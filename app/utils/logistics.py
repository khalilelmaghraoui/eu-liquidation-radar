# app/utils/logistics.py
from app.config import settings

def estimate_shipping_eur(weight_kg: float | None) -> float:
    w = weight_kg if (weight_kg and weight_kg > 0) else 10.0
    return settings.DEFAULT_FIXED_SHIP_EUR + settings.DEFAULT_SHIP_EUR_PER_KG * w

def apply_fees(price_eur: float) -> float:
    return price_eur * settings.DEFAULT_FEES_PCT
