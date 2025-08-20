from app.models import UserTrustStats
from typing import Tuple

def calculate_trust_level_change(
    current_trust_level: float,
    arrival_status: str,
    current_streak: int,
    total_plans: int
) -> Tuple[float, str]:
    """
    Calculate trust level changes (AGGRESSIVE VERSION)
    
    Basic change amounts:
        On-time arrival: +8.0%
        Late: -12.0%
        No arrival: -20.0%
    Consecutive success/failure bonus/penalty:
    Consecutive on-time arrivals: Maximum +15% bonus
    Consecutive success broken by lateness: Maximum -10% penalty
    Consecutive success broken by no-show: Maximum -15% penalty
    Stabilization through experience:
        Reduced experience stabilization for more dramatic changes
        Maximum 25% change reduction for 20+ plans
    Range limits:
        Trust level stays within 0-100% range
        Larger changes allowed for more dramatic impact
    
    Args:
        current_trust_level: Current trust level (0-100)
        arrival_status: Arrival status ("on_time", "late", "not_arrived")
        current_streak: Current consecutive on-time arrivals
        total_plans: Total number of plans
    
    Returns:
        Tuple[float, str]: (New trust level, change explanation)
    """
    # Basic change amount (varies based on consecutive success/failure)
    base_change = 0.0
    explanation = ""

    if arrival_status == "on_time":
        # Case of on-time arrival
        if current_streak > 0:
            # Consecutive success bonus (more aggressive)
            streak_bonus = min(current_streak * 1.5, 15.0)  # Maximum 15% bonus
            base_change = 8.0 + streak_bonus
            explanation = f"On-time arrival ({current_streak} consecutive): +{base_change:.1f}%"
        else:
            base_change = 8.0
            explanation = "On-time arrival: +8.0%"
    
    elif arrival_status == "late":
        # Case of lateness
        if current_streak > 0:
            # Penalty for breaking consecutive success (more aggressive)
            streak_penalty = min(current_streak * 1.0, 10.0)  # Maximum 10% penalty
            base_change = -12.0 - streak_penalty
            explanation = f"Late ({current_streak} consecutive broken): {base_change:.1f}%"
        else:
            base_change = -12.0
            explanation = "Late: -12.0%"
    
    else:  # not_arrived
        # Case of no arrival
        if current_streak > 0:
            # Penalty for breaking consecutive success (more aggressive)
            streak_penalty = min(current_streak * 1.5, 15.0)  # Maximum 15% penalty
            base_change = -20.0 - streak_penalty
            explanation = f"No arrival ({current_streak} consecutive broken): {base_change:.1f}%"
        else:
            base_change = -20.0
            explanation = "No arrival: -20.0%"

    # Adjustment based on total plans (reduced stabilization for more drama)
    if total_plans > 0:
        experience_factor = min(total_plans / 20, 1.0)  # Maximum effect for 20+ plans
        base_change *= (1.0 - experience_factor * 0.25)  # Maximum 25% change reduction

    # Calculate new trust level (keep within 0-100 range)
    new_trust_level = max(0.0, min(100.0, current_trust_level + base_change))

    return new_trust_level, explanation

def update_trust_level(trust_stats: UserTrustStats, arrival_status: str) -> str:
    """
    Update user's trust statistics
    
    Args:
        trust_stats: User's trust statistics
        arrival_status: New arrival status
    
    Returns:
        str: Explanation of trust level change
    """
    # Calculate trust level change
    new_trust_level, explanation = calculate_trust_level_change(
        current_trust_level=trust_stats.trust_level,
        arrival_status=arrival_status,
        current_streak=trust_stats.on_time_streak,
        total_plans=trust_stats.total_plans
    )

    # Update trust statistics
    trust_stats.trust_level = new_trust_level
    trust_stats.last_arrival_status = arrival_status

    return explanation 