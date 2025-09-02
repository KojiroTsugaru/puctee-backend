import asyncio
import logging
from app.db.session import get_db
from app.models import Plan
from app.services.push_notification import send_silent_wakeup_arrival_notification
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

def run_send_silent(plan_id: int):
    """
    既存の内部処理を呼び出す関数。
    EventBridge Scheduler からの自前イベントで silent notification を送信
    """
    async def _async_send_silent():
        async for db in get_db():
            try:
                logger.info(f"[SILENT_NOTIFICATION] Processing scheduled silent notification for plan {plan_id}")
                
                # Get plan and participants
                result = await db.execute(
                    select(Plan).options(selectinload(Plan.participants)).where(Plan.id == plan_id)
                )
                plan = result.scalar_one_or_none()
                
                if not plan:
                    logger.warning(f"[SILENT_NOTIFICATION] Plan {plan_id} not found for silent notification")
                    return {"success": False, "error": "Plan not found"}
                
                logger.info(f"[SILENT_NOTIFICATION] Found plan '{plan.title}' with {len(plan.participants)} participants")
                
                # Send silent notifications to all participants
                notification_count = 0
                for user in plan.participants:
                    if user.push_token:
                        try:
                            logger.info(f"[SILENT_NOTIFICATION] Sending silent notification to user {user.username}")
                            success = await send_silent_wakeup_arrival_notification(
                                device_token=user.push_token,
                                plan_id=plan_id
                            )
                            if success:
                                notification_count += 1
                                logger.info(f"[SILENT_NOTIFICATION] ✅ Silent notification sent successfully to {user.username}")
                            else:
                                logger.warning(f"[SILENT_NOTIFICATION] ❌ Failed to send silent notification to {user.username}")
                        except Exception as e:
                            logger.error(f"[SILENT_NOTIFICATION] ❌ Error sending silent notification to user {user.username}: {e}")
                    else:
                        logger.info(f"[SILENT_NOTIFICATION] User {user.username} has no push token, skipping")
                
                logger.info(f"[SILENT_NOTIFICATION] Silent notification job completed for plan {plan_id}. Sent {notification_count} notifications")
                
                return {
                    "success": True,
                    "plan_id": plan_id,
                    "notifications_sent": notification_count,
                    "total_participants": len(plan.participants)
                }
                
            except Exception as e:
                logger.error(f"Error in run_send_silent for plan {plan_id}: {e}")
                return {"success": False, "error": "Internal server error"}
            finally:
                break
    
    # Use existing event loop if available, create new one if not
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_send_silent())
                return future.result()
        else:
            return loop.run_until_complete(_async_send_silent())
    except RuntimeError:
        # No event loop exists, create new one
        return asyncio.run(_async_send_silent())
