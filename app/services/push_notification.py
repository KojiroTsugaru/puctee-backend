import os
import logging
import ssl
import boto3
import tempfile
from aioapns import APNs, NotificationRequest, PushType
from app.core.config import settings

logger = logging.getLogger(__name__)

class PushNotificationService:
    def __init__(self):
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            # AWS Secrets Managerから認証キーを取得
            sm = boto3.client("secretsmanager")
            resp = sm.get_secret_value(SecretId=settings.APNS_SECRET_ARN)
            key_pem = resp["SecretString"]
            
            # Lambda の /tmp に一時的に書き出し
            with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".p8", delete=False) as tf:
                tf.write(key_pem.encode())
                key_path = tf.name

            # SSLコンテキストの設定
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # APNsクライアントの初期化
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
        badge: int = None
    ) -> bool:
        """
        プッシュ通知を送信する
        
        Args:
            device_token (str): デバイストークン
            title (str): 通知のタイトル
            body (str): 通知の本文
            data (dict, optional): 追加データ
            sound (str, optional): 通知音
            badge (int, optional): バッジ数
            
        Returns:
            bool: 送信成功時はTrue、失敗時はFalse
        """
        try:
            if not self.client:
                self._initialize_client()

            logger.info(f"Sending notification to device token: {device_token}")
            logger.info(f"Notification content - title: {title}, body: {body}")

            # 通知リクエストの作成
            request = NotificationRequest(
                device_token=device_token,
                message={
                    "aps": {
                        "alert": {
                            "title": title,
                            "body": body
                        },
                        "sound": sound,
                        "badge": badge,
                        "content-available": 1
                    },
                    **(data or {})
                },
                push_type=PushType.ALERT
            )

            # 通知の送信
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
        data: dict = None
    ) -> bool:
        """
        サイレントプッシュ通知を送信する
        
        Args:
            device_token (str): デバイストークン
            data (dict, optional): 追加データ
            
        Returns:
            bool: 送信成功時はTrue、失敗時はFalse
        """
        try:
            if not self.client:
                self._initialize_client()

            logger.info(f"Sending silent notification to device token: {device_token}")

            # サイレント通知リクエストの作成
            request = NotificationRequest(
                device_token=device_token,
                message={
                    "aps": {
                        "content-available": 1,
                        "sound": ""
                    },
                    **(data or {})
                },
                push_type=PushType.BACKGROUND
            )

            # 通知の送信
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

# シングルトンインスタンスの作成
push_notification_service = PushNotificationService() 