# app/scrapers/troostwijk.py
import re
from bs4 import BeautifulSoup
from typing import List
from app.scrapers.base import BaseScraper
from app.schemas import RawListing

class TroostwijkScraper(BaseScraper):
    source = "troostwijk"
    base_url = "https://www.troostwijkauctions.com"

    async def search(self, keywords: list[str]) -> List[RawListing]:
        query = "+".join(keywords)
        url = f"{self.base_url}/en/search?query={query}"
        html = await self.fetch_text(url)
        soup = BeautifulSoup(html, "html.parser")

        items = []
        for card in soup.select('[data-testid="listing"] a[href*="/l/"]'):
            href = card.get("href")
            title = card.get_text(" ", strip=True)
            if not href or not title:
                continue
            m = re.search(r"/l/[^/]+-(A1-[\d-]+)", href) or re.search(r"/l/.*?-(\d+)", href)
            external_id = m.group(1) if m else href

            parent = card.find_parent()
            price_text = None
            img = None
            if parent:
                price_el = parent.find(string=re.compile(r"€"))
                price_text = str(price_el) if price_el else None
                img_el = parent.select_one("img")
                img = img_el["src"] if img_el and img_el.has_attr("src") else None

            price_value = _parse_price(price_text) if price_text else 0.0

            items.append(RawListing(
                source=self.source,
                external_id=external_id,
                url=self.base_url + href if href.startswith("/") else href,
                title=title,
                category="sneakers" if "sneaker" in title.lower() or "shoes" in title.lower() else "auction-lot",
                location_name=None,
                lat=None, lon=None,
                photo_url=img,
                currency="EUR",
                price_value=price_value,
                unit_count=None, weight_kg=None,
                posted_at=None
            ))
        return items

def _parse_price(text: str) -> float:
    if not text:
        return 0.0
    cleaned = text.replace("\xa0", " ").replace(".", "").replace(",", ".")
    m = re.search(r"€\s*([0-9]+(?:\.[0-9]+)?)", cleaned)
    try:
        return float(m.group(1)) if m else 0.0
    except Exception:
        return 0.0
