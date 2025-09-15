# app/workers.py
from app.config import settings  # noqa: F401
from app.scrapers.troostwijk import TroostwijkScraper
from app.scrapers.vavato import VavatoScraper
from app.services.ingest import upsert_listings

async def run_scrape_cycle():
    keywords = ["sneaker", "shoes", "nike", "adidas"]
    scrapers = [TroostwijkScraper(), VavatoScraper()]
    all_raw = []
    for s in scrapers:
        try:
            items = await s.search(keywords)
            all_raw.extend(items)
        except Exception as e:
            print(f"[scrape:{s.source}] error: {e}")
    # Base lat/lon currently from global settings (Marseille) via normalizer call
    from app.config import settings as _s
    await upsert_listings(all_raw, _s.BASE_LAT, _s.BASE_LON)
