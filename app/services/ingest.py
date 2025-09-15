# app/services/ingest.py
from typing import List
from sqlalchemy import select
from app.schemas import RawListing
from app.models import Listing
from app.db import SessionLocal
from app.normalizer import normalize_and_snapshot

async def upsert_listings(raws: List[RawListing], base_lat: float, base_lon: float) -> int:
    count = 0
    async with SessionLocal() as s:
        for raw in raws:
            snap = normalize_and_snapshot(raw, base_lat, base_lon)
            q = select(Listing).where(Listing.source == snap["source"], Listing.external_id == snap["external_id"])
            res = await s.execute(q)
            existing = res.scalar_one_or_none()
            if existing:
                for k, v in snap.items():
                    setattr(existing, k, v)
                count += 1
            else:
                s.add(Listing(**snap))
                count += 1
        await s.commit()
    return count
