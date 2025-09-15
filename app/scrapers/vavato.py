# app/scrapers/vavato.py
import re
from bs4 import BeautifulSoup
from typing import List
from app.scrapers.base import BaseScraper
from app.schemas import RawListing

class VavatoScraper(BaseScraper):
    source = "vavato"
    base_url = "https://www.vavato.com"

    async def search(self, keywords: list[str]) -> List[RawListing]:
        query = "+".join(keywords)
        url = f"{self.base_url}/en/search?q={query}"
        html = await self.fetch_text(url)
        soup = BeautifulSoup(html, "html.parser")

        items = []
        for card in soup.select("a[href*='/en/lots/']"):
            href = card.get("href")
            title_el = card.select_one("h3, h2") or card
            title = title_el.get_text(" ", strip=True) if title_el else None
            if not href or not title:
                continue
            external_id = href.split("/")[-1]
            img_el = card.select_one("img")
            img = img_el["src"] if img_el and img_el.has_attr("src") else None
            price_el = card.find(string=re.compile(r"€"))
            price_value = _parse_price(price_el) if price_el else 0.0

            items.append(RawListing(
                source=self.source,
                external_id=external_id,
                url=self.base_url + href if href.startswith("/") else href,
                title=title,
                category="sneakers" if any(k in title.lower() for k in ("sneaker","shoes","trainer")) else "auction-lot",
                location_name=None, lat=None, lon=None,
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
    cleaned = str(text).replace("\xa0", " ").replace(".", "").replace(",", ".")
    m = re.search(r"€\s*([0-9]+(?:\.[0-9]+)?)", cleaned)
    try:
        return float(m.group(1)) if m else 0.0
    except Exception:
        return 0.0
