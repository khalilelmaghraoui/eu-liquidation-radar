# app/schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RawListing(BaseModel):
    source: str
    external_id: str
    url: str
    title: str
    category: Optional[str] = None
    location_name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    photo_url: Optional[str] = None
    currency: str = "EUR"
    price_value: float
    unit_count: Optional[int] = None
    weight_kg: Optional[float] = None
    posted_at: Optional[datetime] = None
