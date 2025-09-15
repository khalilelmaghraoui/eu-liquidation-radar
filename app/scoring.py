# app/scoring.py
from datetime import datetime, timezone

def recency_boost(created_at: datetime | None) -> float:
    if not created_at:
        return 1.0
    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600.0
    if age_hours < 6:
        return 1.15
    if age_hours < 24:
        return 1.08
    if age_hours < 72:
        return 1.02
    return 1.0

def final_rank_score(flip_score: float | None, created_at: datetime | None) -> float:
    base = flip_score or 0.0
    return base * recency_boost(created_at)
