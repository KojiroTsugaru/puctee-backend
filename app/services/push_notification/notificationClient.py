import os
import logging
import ssl
import boto3
import tempfile
from aioapns import APNs, NotificationRequest, PushType
from app.core.config import settings

logger = logging.getLogger(__name__)

class notificationClient:
    def __init__(self):
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            # Get authentication key from AWS Secrets Manager
            sm = boto3.client("secretsmanager")
            resp = sm.get_secret_value(SecretId=settings.APNS_SECRET_ARN)
            key_pem = resp["SecretString"]
            
            # Temporarily write to Lambda's /tmp directory
            with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".p8", delete=False) as tf:
                tf.write(key_pem.encode())
                key_path = tf.name

            # SSL context configuration
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Initialize APNs client
            self.client = APNs(
                key=key_path,
                key_id=settings.APNS_AUTH_KEY_ID,
                team_id=settings.APNS_TEAM_ID,
                topic=settings.APNS_BUNDLE_ID,
                use_sandbox=settings.APNS_USE_SANDBOX,
                ssl_context=ssl_context
            )

            logger.info("Successfully initialized APNs client")
        except Exception as e:
            logger.error(f"Failed to initialize APNs client: {str(e)}", exc_info=True)
            raise

    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: dict = None,
        sound: str = "default",
        badge: int = None,
        category: str = None
    ) -> bool:
        """
        Send push notification
        
        Args:
            device_token (str): Device token
            title (str): Notification title
            body (str): Notification body
            data (dict, optional): Additional data
            sound (str, optional): Notification sound
            badge (int, optional): Badge count
            category (str, optional): Notification category identifier
            
        Returns:
            bool: True on successful send, False on failure
        """
        try:
            if not self.client:
                self._initialize_client()

            logger.info(f"Sending notification to device token: {device_token}")
            logger.info(f"Notification content - title: {title}, body: {body}")

            # Create notification request
            aps_payload = {
                "alert": {
                    "title": title,
                    "body": body
                },
                "sound": sound,
                "badge": badge,
            }
            
            # Add category to aps if provided
            if category:
                aps_payload["category"] = category
            
            request = NotificationRequest(
                device_token=device_token,
                message={
                    "aps": aps_payload,
                    **(data or {})
                },
                push_type=PushType.ALERT
            )

            # Send notification
            logger.info("Sending notification request...")
            response = await self.client.send_notification(request)
            
            if response.is_successful:
                logger.info(f"Successfully sent notification to {device_token}")
                return True
            else:
                logger.error(f"Failed to send notification: {response.description}")
                return False

        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}", exc_info=True)
            return False

    async def send_silent_notification(
        self,
        device_token: str,
        data: dict = None,
        category: str = None
    ) -> bool:
        """
        Send silent push notification
        
        Args:
            device_token (str): Device token
            data (dict, optional): Additional data
            category (str, optional): Notification category identifier
            
        Returns:
            bool: True on successful send, False on failure
        """
        try:
            if not self.client:
                self._initialize_client()

            logger.info(f"Sending silent notification to device token: {device_token}")

            # Create silent notification request
            aps_payload = {
                "content-available": 1
            }
            
            # Add category to aps if provided
            if category:
                aps_payload["category"] = category
            
            request = NotificationRequest(
                device_token=device_token,
                message={
                    "aps": aps_payload,
                    **(data or {})
                },
                push_type=PushType.BACKGROUND,
                priority=5
            )

            # Send notification
            logger.info("Sending silent notification request...")
            response = await self.client.send_notification(request)
            
            if response.is_successful:
                logger.info(f"Successfully sent silent notification to {device_token}")
                return True
            else:
                logger.error(f"Failed to send silent notification: {response.description}")
                return False

        except Exception as e:
            logger.error(f"Error sending silent push notification: {str(e)}", exc_info=True)
            return False