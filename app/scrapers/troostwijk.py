# app/scrapers/troostwijk.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper
from app.schemas import RawListing

UUID_RE = r"[0-9a-fA-F-]{36}"

@dataclass
class TrooTopCategory:
    name: str
    slug: str
    uuid: str  # REQUIRED for top pages to resolve (slug-only 404s)

@dataclass
class TrooSubCategory:
    top_slug: str
    sub_slug: str
    uuid: str
    name: str
    url: str

class TroostwijkScraper(BaseScraper):
    source = "troostwijk"
    base_url = "https://www.troostwijkauctions.com"

    # Stable top categories with UUIDs
    TOP_CATEGORIES: list[TrooTopCategory] = [
        TrooTopCategory("Agricultural", "agricultural", "ca789c2c-b997-4f21-81d4-0bf285aca622"),
        TrooTopCategory("Construction & Earthmoving", "construction-and-earthmoving", "f77365fe-eaa8-42d1-97fc-b14d0111160c"),
        TrooTopCategory("Metalworking", "metalworking", "0d91005a-fa8e-4e8f-98b1-f4854018329f"),
        TrooTopCategory("Food industry", "food-industry", "56dcb02b-18a2-4f41-b002-2009beddbee5"),
        TrooTopCategory("Transport & Logistics", "transport-and-logistics", "22430513-5e00-4758-9889-a4e52c0bb221"),
        TrooTopCategory("Woodworking", "woodworking", "41176767-df26-4cea-80b5-3024e6ab4916"),
        TrooTopCategory("Retail & Office", "retail-and-office", "256d5fe2-d104-485f-a332-cfb61fd0d56c"),
        TrooTopCategory("More industrial categories", "more-industrial-categories", "6319e404-42d1-4701-87a1-7597c57a4907"),
        TrooTopCategory("Art & Antiques", "art", "34fcdec2-39f3-4248-8569-4c08ed4dd03e"),
        TrooTopCategory("Clothing, shoes, accessories", "clothing-shoes-accessories", "5e9116de-6c73-484b-a136-f2ce256ff11d"),
    ]

    async def list_top_categories(self) -> list[TrooTopCategory]:
        return self.TOP_CATEGORIES

    async def list_subcategories(self, top_slug: str, top_uuid: str) -> list[TrooSubCategory]:
        """
        Scrape subcategories from /en/c/<top_slug>/<top_uuid>
        by finding links like /en/c/<top>/<sub>/<uuid>
        """
        url = f"{self.base_url}/en/c/{top_slug}/{top_uuid}"
        html = await self.fetch_text(url)
        soup = BeautifulSoup(html, "html.parser")

        subs: list[TrooSubCategory] = []
        for a in soup.select("a[href^='/en/c/']"):
            href = a.get("href") or ""
            # ex: /en/c/clothing-shoes-accessories/men%27s-clothing/<uuid>
            m = re.match(rf"^/en/c/{re.escape(top_slug)}/([^/]+)/({UUID_RE})(?:/|$|\?)", href)
            if not m:
                continue
            sub_slug, uuid = m.group(1), m.group(2)
            name = a.get_text(" ", strip=True)
            url_full = urljoin(self.base_url, href)

            # de-dup
            if not any(sc.sub_slug == sub_slug and sc.uuid == uuid for sc in subs):
                subs.append(
                    TrooSubCategory(
                        top_slug=top_slug,
                        sub_slug=sub_slug,
                        uuid=uuid,
                        name=name,
                        url=url_full,
                    )
                )
        return subs

    async def fetch_lots_in_category(self, top_slug: str, top_uuid: str, limit: int = 10) -> list[RawListing]:
        """Fallback: fetch lots directly on top category page."""
        url = f"{self.base_url}/en/c/{top_slug}/{top_uuid}"
        return await self._parse_lots_from_page(url, category=f"{top_slug}", limit=limit)

    async def fetch_lots_in_subcategory(self, top_slug: str, sub_slug: str, uuid: str, limit: int = 10) -> list[RawListing]:
        url = f"{self.base_url}/en/c/{top_slug}/{sub_slug}/{uuid}"
        return await self._parse_lots_from_page(url, category=f"{top_slug}/{sub_slug}", limit=limit)

    async def _parse_lots_from_page(self, url: str, category: str, limit: int = 10) -> list[RawListing]:
        html = await self.fetch_text(url)
        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select("[data-testid='listing']") or soup.select("a[href*='/l/']")
        items: list[RawListing] = []

        for card in cards:
            a = card.select_one("a[href*='/l/']") or (card if card.name == "a" else None)
            if not a:
                continue
            href = a.get("href") or ""
            url_full = urljoin(self.base_url, href)

            title = a.get_text(" ", strip=True)[:180]
            if not title:
                continue

            m = re.search(r"/l/[^/]+-(A1-[\d-]+)", href) or re.search(r"/l/.*?-(\d+)", href)
            external_id = m.group(1) if m else href

            img_el = card.select_one("img")
            photo = None
            if img_el:
                photo = img_el.get("src") or img_el.get("data-src") or img_el.get("data-srcset")
                if photo and photo.startswith("//"):
                    photo = "https:" + photo

            price_el = card.find(string=re.compile(r"€")) or card.find("span", string=re.compile("€"))
            price_value = _parse_price(str(price_el)) if price_el else 0.0

            items.append(
                RawListing(
                    source=self.source,
                    external_id=external_id,
                    url=url_full,
                    title=title,
                    category=category,
                    location_name=None,
                    lat=None,
                    lon=None,
                    photo_url=photo,
                    currency="EUR",
                    price_value=price_value,
                    unit_count=None,
                    weight_kg=None,
                    posted_at=None,
                )
            )
            if len(items) >= limit:
                break
        return items


# Optional legacy search kept for keyword flows
class _LegacyTroostwijkSearch(TroostwijkScraper):
    async def search(self, keywords: list[str]) -> List[RawListing]:
        query = "+".join(keywords)
        url = f"{self.base_url}/en/search?query={query}"
        html = await self.fetch_text(url)
        soup = BeautifulSoup(html, "html.parser")

        items = []
        for card in soup.select("[data-testid='listing'] a[href*='/l/']"):
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

            items.append(
                RawListing(
                    source=self.source,
                    external_id=external_id,
                    url=self.base_url + href if href.startswith("/") else href,
                    title=title,
                    category="search",
                    location_name=None,
                    lat=None,
                    lon=None,
                    photo_url=img,
                    currency="EUR",
                    price_value=price_value,
                    unit_count=None,
                    weight_kg=None,
                    posted_at=None,
                )
            )
        return items


def _parse_price(text: str | None) -> float:
    if not text:
        return 0.0
    cleaned = str(text).replace("\xa0", " ").replace(".", "").replace(",", ".")
    m = re.search(r"€\s*([0-9]+(?:\.[0-9]+)?)", cleaned)
    try:
        return float(m.group(1)) if m else 0.0
    except Exception:
        return 0.0
