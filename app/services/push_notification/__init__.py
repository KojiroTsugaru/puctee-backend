from app.services.push_notification.notificationClient import notificationClient

# Create singleton instance
push_notification_client = notificationClient()

# Send friend invite notification
async def send_friend_invite_notification(device_token: str, sender_username: str, invite_id: int) -> bool:
    """
    Send friend invite notification
    
    Args:
        device_token (str): Device token
        sender_username (str): Username of the user who sent the invite
        invite_id (int): Invite ID
        
    Returns:
        bool: True on successful send, False on failure
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

# Send plan invite notification
async def send_plan_invite_notification(device_token: str, title: str, body: str) -> bool:
    """
    Send plan invite notification
    
    Args:
        device_token (str): Device token
        title (str): Notification title
        body (str): Notification body
        
    Returns:
        bool: True on successful send, False on failure
    """
    return await push_notification_client.send_notification(
        device_token=device_token,
        title=title,       
        body=body,
        data={"type": "plan_invite"}
    )
