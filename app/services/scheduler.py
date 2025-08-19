# app/services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone
from app.services.push_notification import send_silent_wakeup_arrival_notification
from app.db.session import get_db
from app.models import Plan, User
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import logging

# Configure logging to show in console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures logs appear in console
    ]
)

logger = logging.getLogger(__name__)

# Enable APScheduler logging to see job execution details
apscheduler_logger = logging.getLogger('apscheduler')
apscheduler_logger.setLevel(logging.INFO)

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()

def job_id(plan_id: int) -> str:
    return f"plan-silent-{plan_id}"

async def schedule_silent_for_plan(plan_id: int, when_utc: datetime):
    # 既存ジョブがあれば置き換え
    jid = job_id(plan_id)
    try:
        scheduler.remove_job(jid)
        logger.info(f"Removed existing job {jid}")
    except Exception as e:
        logger.info(f"No existing job to remove for {jid}: {e}")
    
    logger.info(f"Scheduling silent notification for plan {plan_id} at {when_utc} (UTC)")
    scheduler.add_job(send_silent_job, "date", id=jid, run_date=when_utc, args=[plan_id])
    
    # Log all scheduled jobs for debugging
    jobs = scheduler.get_jobs()
    logger.info(f"Total scheduled jobs: {len(jobs)}")
    for job in jobs:
        logger.info(f"Job {job.id}: next run at {job.next_run_time}")

async def cancel_silent_for_plan(plan_id: int):
    try:
        scheduler.remove_job(job_id(plan_id))
    except Exception:
        pass

async def send_silent_job(plan_id: int):
    logger.info(f"Executing silent notification job for plan {plan_id}")
    
    # DBから対象プランと参加者のデバイストークンを引く
    async for db in get_db():
        try:
            result = await db.execute(
                select(Plan).options(selectinload(Plan.participants)).where(Plan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
            if not plan:
                logger.warning(f"Plan {plan_id} not found for silent notification")
                return
            
            logger.info(f"Found plan '{plan.title}' with {len(plan.participants)} participants")
            
            # 参加者それぞれに投げる
            notification_count = 0
            for user in plan.participants:
                if user.push_token:
                    try:
                        logger.info(f"Sending silent notification to user {user.username}")
                        await send_silent_wakeup_arrival_notification(
                            device_token=user.push_token,
                            plan_id=plan_id
                        )
                        notification_count += 1
                        logger.info(f"Silent notification sent successfully to {user.username}")
                    except Exception as e:
                        logger.error(f"APNs silent failed for user {user.username}: {e}")
                else:
                    logger.info(f"User {user.username} has no push token, skipping")
            
            logger.info(f"Silent notification job completed for plan {plan_id}. Sent {notification_count} notifications")
            
        except Exception as e:
            logger.error(f"Error in send_silent_job for plan {plan_id}: {e}")
        finally:
            await db.close()
        break  # Only process once
