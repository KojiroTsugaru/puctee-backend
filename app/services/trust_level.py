from app.models import UserTrustStats
from typing import Tuple

def calculate_trust_level_change(
    current_trust_level: float,
    arrival_status: str,
    current_streak: int,
    total_plans: int
) -> Tuple[float, str]:
    """
    信頼度レベルの変化を計算する
    
    基本の変化量：
        時間通り到着: +2.0%
        遅刻: -3.0%
        未到着: -5.0%
    連続成功/失敗のボーナス/ペナルティ：
    時間通り到着の連続成功: 最大+5%のボーナス
    遅刻による連続成功途切れ: 最大-3%のペナルティ
    未到着による連続成功途切れ: 最大-4%のペナルティ
    経験値による安定化：
        総プラン数が増えるほど、信頼度の変化が緩やかに
        10回以上のプランで最大50%の変化量削減
    範囲制限：
        信頼度レベルは0-100%の範囲に収まる
        変化量に上限を設けて急激な変動を防止
    
    Args:
        current_trust_level: 現在の信頼度レベル(0-100)
        arrival_status: 到着状況（"on_time", "late", "not_arrived"）
        current_streak: 現在の連続時間通り到着数
        total_plans: 総プラン数
    
    Returns:
        Tuple[float, str]: (新しい信頼度レベル, 変化の説明)
    """
    # 基本の変化量（連続成功/失敗に応じて変化）
    base_change = 0.0
    explanation = ""

    if arrival_status == "on_time":
        # 時間通り到着の場合
        if current_streak > 0:
            # 連続成功ボーナス
            streak_bonus = min(current_streak * 0.5, 5.0)  # 最大5%のボーナス
            base_change = 2.0 + streak_bonus
            explanation = f"時間通り到着（{current_streak}回連続）: +{base_change:.1f}%"
        else:
            base_change = 2.0
            explanation = "時間通り到着: +2.0%"
    
    elif arrival_status == "late":
        # 遅刻の場合
        if current_streak > 0:
            # 連続成功が途切れるペナルティ
            streak_penalty = min(current_streak * 0.3, 3.0)  # 最大3%のペナルティ
            base_change = -3.0 - streak_penalty
            explanation = f"遅刻（{current_streak}回連続が途切れる）: {base_change:.1f}%"
        else:
            base_change = -3.0
            explanation = "遅刻: -3.0%"
    
    else:  # not_arrived
        # 未到着の場合
        if current_streak > 0:
            # 連続成功が途切れるペナルティ
            streak_penalty = min(current_streak * 0.4, 4.0)  # 最大4%のペナルティ
            base_change = -5.0 - streak_penalty
            explanation = f"未到着（{current_streak}回連続が途切れる）: {base_change:.1f}%"
        else:
            base_change = -5.0
            explanation = "未到着: -5.0%"

    # 総プラン数に基づく調整（経験値による安定化）
    if total_plans > 0:
        experience_factor = min(total_plans / 10, 1.0)  # 10回以上のプランで最大効果
        base_change *= (1.0 - experience_factor * 0.5)  # 最大50%の変化量削減

    # 新しい信頼度レベルを計算(0-100の範囲に収める)
    new_trust_level = max(0.0, min(100.0, current_trust_level + base_change))

    return new_trust_level, explanation

def update_trust_level(trust_stats: UserTrustStats, arrival_status: str) -> str:
    """
    ユーザーの信頼度統計を更新する
    
    Args:
        trust_stats: ユーザーの信頼度統計
        arrival_status: 新しい到着状況
    
    Returns:
        str: 信頼度レベルの変化の説明
    """
    # 信頼度レベルの変化を計算
    new_trust_level, explanation = calculate_trust_level_change(
        current_trust_level=trust_stats.trust_level,
        arrival_status=arrival_status,
        current_streak=trust_stats.on_time_streak,
        total_plans=trust_stats.total_plans
    )

    # 信頼度統計を更新
    trust_stats.trust_level = new_trust_level
    trust_stats.last_arrival_status = arrival_status

    return explanation 