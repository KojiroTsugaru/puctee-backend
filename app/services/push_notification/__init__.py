from app.services.push_notification.notificationClient import notificationClient

# シングルトンインスタンスの作成
push_notification_client = notificationClient()

# 便利な関数をエクスポート
async def send_friend_invite_notification(device_token: str, sender_username: str, invite_id: int) -> bool:
    """
    フレンド招待通知を送信する
    
    Args:
        device_token (str): デバイストークン
        sender_username (str): 招待を送信したユーザーのユーザー名
        invite_id (int): 招待ID
        
    Returns:
        bool: 送信成功時はTrue、失敗時はFalse
    """
    return await push_notification_client.send_notification(
        device_token=device_token,
        title="New Friend Request",
        body=f"{sender_username} sent you a friend request",
        data={
            "type": "friend_invite",
            "invite_id": invite_id
        }
    ) 