import json
import logging
from mangum import Mangum
from app.main import app
from app.services.scheduler.silent_notification import run_send_silent

# Configure logging for Lambda - Force INFO level
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Remove existing handlers and add new one
for handler in root_logger.handlers:
    root_logger.removeHandler(handler)

# Add console handler with INFO level
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root_logger.addHandler(handler)

logger = logging.getLogger(__name__)

_asgi = Mangum(app)

def handler(event, context):
    """
    Lambda handler:
    1) Process custom events {"job":"send_silent","plan_id":...} with highest priority
    2) Delegate other events to FastAPI as API Gateway compatible events
    """
    # A. Handle string events from EventBridge Scheduler
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except Exception:
            pass

    # B. Handle custom events directly without FastAPI
    if isinstance(event, dict) and event.get("job") == "send_silent":
        plan_id = event.get("plan_id")
        schedule_name = event.get("schedule", "unknown")
        
        logger.info(f"[LAMBDA_HANDLER] Processing EventBridge Scheduler event: plan_id={plan_id}, schedule={schedule_name}")
        
        try:
            plan_id = int(plan_id)
        except Exception:
            logger.error(f"[LAMBDA_HANDLER] Invalid plan_id: {plan_id}")
            return {
                "statusCode": 400,
                "body": json.dumps({"ok": False, "error": "invalid plan_id"})
            }   
        try:
            logger.info(f"[LAMBDA_HANDLER] Starting silent notification job for plan {plan_id}")
            result = run_send_silent(plan_id)
            logger.info(f"[LAMBDA_HANDLER] Silent notification job completed for plan {plan_id}: {result}")
            return {"statusCode": 200, "body": json.dumps(result)}
        except Exception as e:
            logger.exception(f"[LAMBDA_HANDLER] send_silent failed for plan {plan_id}: %s", e)
            return {"statusCode": 500, "body": json.dumps({"ok": False, "error": "internal"})}

    # C. Delegate other events (API Gateway/Function URL) to FastAPI
    #    Add missing sourceIp to prevent Mangum KeyError
    if isinstance(event, dict) and "requestContext" in event:
        rc = event["requestContext"]
        if isinstance(rc, dict) and "http" in rc and isinstance(rc["http"], dict):
            rc["http"].setdefault("sourceIp", "0.0.0.0")

    return _asgi(event, context)