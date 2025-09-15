# app/normalizer.py
from app.schemas import RawListing
from app.utils.geo import haversine_km
from app.utils.logistics import estimate_shipping_eur, apply_fees
from app.config import settings

def normalize_and_snapshot(raw: RawListing, base_lat: float, base_lon: float) -> dict:
    distance_km = haversine_km(base_lat, base_lon, raw.lat, raw.lon)
    price_per_unit = (raw.price_value / raw.unit_count) if (raw.unit_count and raw.unit_count > 0) else None
    price_per_kg = (raw.price_value / raw.weight_kg) if (raw.weight_kg and raw.weight_kg > 0) else None

    fees = apply_fees(raw.price_value)
    shipping = estimate_shipping_eur(raw.weight_kg)
    total_cost = raw.price_value + fees + shipping

    resale_multiplier = 1.35 if (raw.category and "sneaker" in raw.category.lower()) or ("sneaker" in raw.title.lower()) else 1.2
    resale_gross = raw.price_value * resale_multiplier
    margin = resale_gross - total_cost

    margin_pct = (margin / total_cost) if total_cost > 0 else 0
    dist_penalty = 1.0
    if distance_km:
        if distance_km > 1500:
            dist_penalty = 0.6
        elif distance_km > 800:
            dist_penalty = 0.75
        elif distance_km > 400:
            dist_penalty = 0.85

    flip_score = max(0.0, (0.6 * margin_pct + 0.4 * (margin / 100.0))) * dist_penalty

    snapshot = dict(
        source=raw.source,
        external_id=raw.external_id,
        url=raw.url,
        title=raw.title.strip(),
        category=raw.category,
        location_name=raw.location_name,
        lat=raw.lat,
        lon=raw.lon,
        photo_url=raw.photo_url,
        currency=raw.currency,
        price_eur=raw.price_value,
        unit_count=raw.unit_count,
        weight_kg=raw.weight_kg,
        posted_at=raw.posted_at,
        price_per_unit=price_per_unit,
        price_per_kg=price_per_kg,
        distance_km=distance_km,
        fees_pct=settings.DEFAULT_FEES_PCT,
        ship_estimate_eur=shipping,
        margin_estimate_eur=margin,
        flip_score=flip_score,
        raw=raw.model_dump(),
    )
    return snapshot
