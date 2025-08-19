from app.services.push_notification.notificationClient import notificationClient
from app.models import Plan

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
            "invite_id": invite_id,
            "category": "FRIEND_INVITE"
        }
    )

# Send plan invite notification
async def send_plan_invite_notification(device_token: str, title: str, body: str, plan_id: int = None) -> bool:
    """
    Send plan invite notification
    
    Args:
        device_token (str): Device token
        title (str): Notification title
        body (str): Notification body
        plan_id (int, optional): Plan ID
        
    Returns:
        bool: True on successful send, False on failure
    """
    data = {"category": "PLAN_INVITE"}
    if plan_id:
        data["plan_id"] = plan_id
        
    return await push_notification_client.send_notification(
        device_token=device_token,
        title=title,       
        body=body,
        data=data
    )
    
# Send silent wakeup notification
async def send_silent_wakeup_arrival_notification(device_token: str, plan_id: int) -> bool:
    """
    Send silent wakeup notification for arrival checking
    
    Args:
        device_token (str): Device token
        plan_id (int): Plan ID
        
    Returns:
        bool: True on successful send, False on failure
    """
    # サイレント：alert/sound/badgeなし、content-available=1
    return await push_notification_client.send_silent_notification(
        device_token=device_token,
        category="PLAN_ARRIVAL_WAKEUP",
        data={
            "plan_id": plan_id
        }
    )
    
# Send arrival check notification
async def send_arrival_check_notification(plan: Plan, device_token: str, is_arrived: bool) -> bool:
    """
    Send arrival check notification
    
    Args:
        device_token (str): Device token
        plan_id (int): Plan ID
        is_arrived (bool): Whether the user has arrived
        
    Returns:
        bool: True on successful send, False on failure
    """
    # Set different title and body based on arrival status
    if is_arrived:
        title = f"Arrival Check - {plan.title}"
        body = f"You've arrived at {plan.locations[0].name} on time 🔥"
    else:
        title = f"Arrival Check - {plan.title}"
        body = f"You didn't make it to {plan.locations[0].name} on time ❌"
    
    return await push_notification_client.send_notification(
        device_token=device_token,
        title=title,
        body=body,
        category="PLAN_ARRIVAL_CHECK",
        data={
            "plan_id": plan.id,
            "is_arrived": is_arrived,
        }
    )
