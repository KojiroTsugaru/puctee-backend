from app.models import UserTrustStats
from typing import Tuple

def calculate_trust_level_change(
    current_trust_level: float,
    arrival_status: str,
    current_streak: int,
    total_plans: int
) -> Tuple[float, str]:
    """
    Calculate trust level changes
    
    Basic change amounts:
        On-time arrival: +2.0%
        Late: -3.0%
        No arrival: -5.0%
    Consecutive success/failure bonus/penalty:
    Consecutive on-time arrivals: Maximum +5% bonus
    Consecutive success broken by lateness: Maximum -3% penalty
    Consecutive success broken by no-show: Maximum -4% penalty
    Stabilization through experience:
        The more total plans, the more gradual trust level changes become
        Maximum 50% change reduction for 10+ plans
    Range limits:
        Trust level stays within 0-100% range
        Change amount capped to prevent sudden fluctuations
    
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
            # Consecutive success bonus
            streak_bonus = min(current_streak * 0.5, 5.0)  # Maximum 5% bonus
            base_change = 2.0 + streak_bonus
            explanation = f"On-time arrival ({current_streak} consecutive): +{base_change:.1f}%"
        else:
            base_change = 2.0
            explanation = "On-time arrival: +2.0%"
    
    elif arrival_status == "late":
        # Case of lateness
        if current_streak > 0:
            # Penalty for breaking consecutive success
            streak_penalty = min(current_streak * 0.3, 3.0)  # Maximum 3% penalty
            base_change = -3.0 - streak_penalty
            explanation = f"Late ({current_streak} consecutive broken): {base_change:.1f}%"
        else:
            base_change = -3.0
            explanation = "Late: -3.0%"
    
    else:  # not_arrived
        # Case of no arrival
        if current_streak > 0:
            # Penalty for breaking consecutive success
            streak_penalty = min(current_streak * 0.4, 4.0)  # Maximum 4% penalty
            base_change = -5.0 - streak_penalty
            explanation = f"No arrival ({current_streak} consecutive broken): {base_change:.1f}%"
        else:
            base_change = -5.0
            explanation = "No arrival: -5.0%"

    # Adjustment based on total plans (stabilization through experience)
    if total_plans > 0:
        experience_factor = min(total_plans / 10, 1.0)  # Maximum effect for 10+ plans
        base_change *= (1.0 - experience_factor * 0.5)  # Maximum 50% change reduction

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