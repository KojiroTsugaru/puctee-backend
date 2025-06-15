import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models import Plan, User
from app.services.push_notification import push_notification_service

logger = logging.getLogger(__name__)

class PlanScheduler:
    def __init__(self):
        self.running = False
        self.check_interval = 60  # 1分ごとにチェック

    async def start(self):
        """スケジューラーを開始する"""
        if self.running:
            return

        self.running = True
        logger.info("Plan scheduler started")
        
        while self.running:
            try:
                await self._check_plans()
            except Exception as e:
                logger.error(f"Error in plan scheduler: {str(e)}", exc_info=True)
            
            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """スケジューラーを停止する"""
        self.running = False
        logger.info("Plan scheduler stopped")

    async def _check_plans(self):
        """開始時刻が近づいているプランをチェックし、通知を送信する"""
        async with AsyncSessionLocal() as session:
            try:
                # 現在時刻から1分以内に開始するプランを取得
                now = datetime.now(timezone.utc)
                check_time = now - timedelta(seconds=self.check_interval)
                query = select(Plan).where(
                    Plan.start_time <= now,
                    Plan.start_time > check_time
                )
                result = await session.execute(query)
                plans = result.scalars().all()

                for plan in plans:
                    await self._send_start_notifications(plan, session)
            except Exception as e:
                logger.error(f"Error checking plans: {str(e)}", exc_info=True)
                await session.rollback()
            finally:
                await session.close()

    async def _send_start_notifications(self, plan: Plan, session: AsyncSession):
        """プランの参加者全員に開始通知を送信する"""
        try:
            # プランの参加者を取得（JOINを使用して一度のクエリで取得）
            query = select(User).join(
                plan.participants.relationship.property.mapper.class_,
                User.id == plan.participants.relationship.property.mapper.class_.user_id
            ).where(
                plan.participants.relationship.property.mapper.class_.plan_id == plan.id
            )
            result = await session.execute(query)
            participants = result.scalars().all()

            # 各参加者に通知を送信
            for participant in participants:
                if participant.push_token:
                    await push_notification_service.send_silent_notification(
                        device_token=participant.push_token,
                        data={
                            "type": "plan_start",
                            "plan_id": plan.id,
                            "plan_title": plan.title
                        }
                    )

            logger.info(f"Sent start notifications for plan {plan.id}")
        except Exception as e:
            logger.error(f"Error sending start notifications for plan {plan.id}: {str(e)}", exc_info=True)

# シングルトンインスタンスの作成
plan_scheduler = PlanScheduler() 