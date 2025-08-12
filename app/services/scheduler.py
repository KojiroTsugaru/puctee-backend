import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models import Plan, User
from app.services.push_notification.notificationClient import notificationClient

logger = logging.getLogger(__name__)

class PlanScheduler:
    def __init__(self):
        self.running = False
        self.check_interval = 60  # Check every 1 minute

    async def start(self):
        """Start the scheduler"""
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
        """Stop the scheduler"""
        self.running = False
        logger.info("Plan scheduler stopped")

    async def _check_plans(self):
        """Check for plans with approaching start times and send notifications"""
        async with AsyncSessionLocal() as session:
            try:
                # Get plans that start within 1 minute from current time
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
        """Send start notifications to all plan participants"""
        try:
            # Get plan participants (using JOIN for single query retrieval)
            query = select(User).join(
                plan.participants.relationship.property.mapper.class_,
                User.id == plan.participants.relationship.property.mapper.class_.user_id
            ).where(
                plan.participants.relationship.property.mapper.class_.plan_id == plan.id
            )
            result = await session.execute(query)
            participants = result.scalars().all()

            # Send notification to each participant
            for participant in participants:
                if participant.push_token:
                    await notificationClient.send_silent_notification(
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

# Create singleton instance
plan_scheduler = PlanScheduler() 