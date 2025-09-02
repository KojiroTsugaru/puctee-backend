import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

import boto3
from app.core.config import settings

logger = logging.getLogger(__name__)

SCHEDULE_GROUP = "default"

class EventBridgeSchedulerService:
    def __init__(self):
        self.client = boto3.client('scheduler', region_name=settings.AWS_REGION)
        self.lambda_arn = f"arn:aws:lambda:{settings.AWS_REGION}:002066576827:function:puctee-app"
        self.role_arn = "arn:aws:iam::002066576827:role/puctee-scheduler-invoke-role"
        self.dlq_sqs_arn = "arn:aws:sqs:ap-northeast-1:002066576827:puctee-scheduler-dlq"

    def _get_schedule_name(self, plan_id: int) -> str:
        return f"puctee-plan-silent-{plan_id}"

    def _ensure_utc_future(self, when_utc: datetime) -> datetime:
        if when_utc.tzinfo is None:
            when_utc = when_utc.replace(tzinfo=timezone.utc)
        else:
            when_utc = when_utc.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        if (when_utc - now) < timedelta(seconds=20):
            when_utc = (now + timedelta(seconds=30)).replace(microsecond=0)
        return when_utc

    async def schedule_silent_notification(self, plan_id: int, when_utc: datetime) -> bool:
        try:
            schedule_name = self._get_schedule_name(plan_id)
            when_utc = self._ensure_utc_future(when_utc)

            ok = await self._delete_schedule_if_exists(schedule_name)
            if not ok:
                logger.warning(f"Delete existing schedule failed: {schedule_name}")

            schedule_expression = f"at({when_utc.strftime('%Y-%m-%dT%H:%M:%S')})"

            payload = {"job": "send_silent", "plan_id": plan_id, "schedule": schedule_name}

            target = {
                "Arn": self.lambda_arn,
                "RoleArn": self.role_arn,
                "Input": json.dumps(payload),
                "RetryPolicy": {
                    "MaximumEventAgeInSeconds": 86400,
                    "MaximumRetryAttempts": 10
                },
            }
            if self.dlq_sqs_arn:
                target["DeadLetterConfig"] = {"Arn": self.dlq_sqs_arn}

            resp = self.client.create_schedule(
                Name=schedule_name,
                GroupName=SCHEDULE_GROUP,
                ScheduleExpression=schedule_expression,
                ScheduleExpressionTimezone="UTC",
                FlexibleTimeWindow={"Mode":  "OFF"},
                Target=target,
                State="ENABLED",
                Description=f"Silent notification for plan {plan_id}",
                ClientToken=str(uuid.uuid4()),
            )
            logger.info(f"Created schedule {schedule_name}: {resp.get('ScheduleArn')} at {when_utc.isoformat()}")

            info = self.client.get_schedule(Name=schedule_name, GroupName=SCHEDULE_GROUP)
            logger.info(f"Schedule next={info.get('NextInvocationTime')} last={info.get('LastRunTime')}")

            return True

        except Exception as e:
            logger.exception(f"Failed to schedule silent notification for plan {plan_id}: {e}")
            return False

    async def cancel_silent_notification(self, plan_id: int) -> bool:
        try:
            schedule_name = self._get_schedule_name(plan_id)
            return await self._delete_schedule_if_exists(schedule_name)
        except Exception as e:
            logger.exception(f"Failed to cancel silent notification for plan {plan_id}: {e}")
            return False

    async def _delete_schedule_if_exists(self, schedule_name: str) -> bool:
        try:
            self.client.delete_schedule(Name=schedule_name, GroupName=SCHEDULE_GROUP)
            logger.info(f"Deleted existing schedule: {schedule_name}")
            return True
        except self.client.exceptions.ResourceNotFoundException:
            logger.info(f"No existing schedule to delete: {schedule_name}")
            return True
        except Exception as e:
            logger.exception(f"Failed to delete schedule {schedule_name}: {e}")
            return False


# Facade
eventbridge_scheduler = EventBridgeSchedulerService()

async def schedule_silent_for_plan(plan_id: int, when_utc: datetime) -> bool:
    return await eventbridge_scheduler.schedule_silent_notification(plan_id, when_utc)

async def cancel_silent_for_plan(plan_id: int) -> bool:
    return await eventbridge_scheduler.cancel_silent_notification(plan_id)
