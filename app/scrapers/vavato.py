# app/scrapers/vavato.py
from __future__ import annotations
import re
import json
from dataclasses import dataclass
from typing import List, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper
from app.schemas import RawListing

UUID_RE = r"[0-9a-fA-F-]{36}"

@dataclass
class VTopCategory:
    name: str
    slug: str
    uuid: str

@dataclass
class VSubCategory:
    name: str
    top_slug: str
    sub_slug: str
    uuid: str
    url: str

class VavatoScraper(BaseScraper):
    source = "vavato"
    base_url = "https://www.vavato.com"

    # -------------------- category discovery --------------------

    async def list_top_categories(self) -> List[VTopCategory]:
        """Discover top categories from the homepage by finding anchors like /en/c/<slug>/<uuid>."""
        try:
            html = await self.fetch_text(self.base_url + "/en")
        except Exception:
            return []

        soup = BeautifulSoup(html, "html.parser")
        found: dict[tuple[str, str], VTopCategory] = {}

        for a in soup.select("a[href^='/en/c/']"):
            href = a.get("href") or ""
            m = re.match(rf"^/en/c/([^/]+)/({UUID_RE})(?:/|$|\?)", href)
            if not m:
                continue
            slug, uuid = m.group(1), m.group(2)
            name = a.get_text(" ", strip=True) or slug.replace("-", " ").title()
            key = (slug, uuid)
            if key not in found:
                found[key] = VTopCategory(name=name, slug=slug, uuid=uuid)

        return list(found.values())

    async def list_subcategories(self, top_slug: str, top_uuid: str) -> List[VSubCategory]:
        """Scrape /en/c/<top_slug>/<top_uuid> and collect deeper links: /en/c/<top>/<sub>/<uuid>."""
        url = f"{self.base_url}/en/c/{top_slug}/{top_uuid}"
        html = await self.fetch_text(url)
        soup = BeautifulSoup(html, "html.parser")

        subs: dict[tuple[str, str], VSubCategory] = {}
        for a in soup.select("a[href^='/en/c/']"):
            href = a.get("href") or ""
            m = re.match(rf"^/en/c/{re.escape(top_slug)}/([^/]+)/({UUID_RE})(?:/|$|\?)", href)
            if not m:
                continue
            sub_slug, uuid = m.group(1), m.group(2)
            name = a.get_text(" ", strip=True) or sub_slug.replace("-", " ").title()
            key = (sub_slug, uuid)
            if key not in subs:
                subs[key] = VSubCategory(
                    name=name,
                    top_slug=top_slug,
                    sub_slug=sub_slug,
                    uuid=uuid,
                    url=urljoin(self.base_url, href),
                )
        return list(subs.values())

    # ------------------------ lot fetching ------------------------

    async def fetch_lots_in_category(self, top_slug: str, top_uuid: str, limit: int = 10) -> List[RawListing]:
        # hint page params to encourage SSR
        url = f"{self.base_url}/en/c/{top_slug}/{top_uuid}?page=1&pageSize=24"
        return await self._parse_lots_from_page(url, category=top_slug, limit=limit)

    async def fetch_lots_in_subcategory(self, top_slug: str, sub_slug: str, uuid: str, limit: int = 10) -> List[RawListing]:
        url = f"{self.base_url}/en/c/{top_slug}/{sub_slug}/{uuid}?page=1&pageSize=24"
        return await self._parse_lots_from_page(url, category=f"{top_slug}/{sub_slug}", limit=limit)

    async def _parse_lots_from_page(self, url: str, category: str, limit: int = 10) -> List[RawListing]:
        try:
            html = await self.fetch_text(url)
        except Exception:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items: list[RawListing] = []

        # 1) Try plain HTML cards first
        cards = soup.select("[data-testid='lot-card'] a[href^='/en/lots/']") or soup.select("a[href^='/en/lots/']")
        for a in cards:
            rl = _raw_from_anchor(self.base_url, a, category)
            if rl:
                items.append(rl)
            if len(items) >= limit:
                break

        if len(items) >= limit:
            return items[:limit]

        # 2) Fallback: parse embedded JSON (Next.js) — look for __NEXT_DATA__ or any JSON blob
        json_items = _extract_lots_from_embedded_json(html, base_url=self.base_url, category=category)
        for rl in json_items:
            # avoid duplicates by external_id
            if any(x.external_id == rl.external_id for x in items):
                continue
            items.append(rl)
            if len(items) >= limit:
                break

        return items[:limit]


# ------------------------- helpers -------------------------

def _raw_from_anchor(base_url: str, a, category: str) -> RawListing | None:
    href = a.get("href") or ""
    if not href.startswith("/en/lots/"):
        return None
    lot_url = urljoin(base_url, href)

    title_el = a.select_one("h3, h2") or a
    title = title_el.get_text(" ", strip=True)[:180] if title_el else None
    if not title:
        return None

    external_id = href.strip("/").split("/")[-1]

    # image: look in the anchor, then in the parent
    img_el = a.select_one("img")
    if not img_el:
        parent = a.find_parent()
        img_el = parent.select_one("img") if parent else None
    photo = None
    if img_el:
        photo = img_el.get("src") or img_el.get("data-src") or img_el.get("data-srcset")
        if photo and photo.startswith("//"):
            photo = "https:" + photo

    # price near the anchor/parent
    host = a.find_parent() or a
    price_el = host.find(string=re.compile(r"€")) or host.find("span", string=re.compile("€"))
    price_value = _parse_price(str(price_el)) if price_el else 0.0

    return RawListing(
        source="vavato",
        external_id=external_id,
        url=lot_url,
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

def _extract_lots_from_embedded_json(html: str, base_url: str, category: str) -> List[RawListing]:
    """
    Try to parse data from embedded JSON (Next.js __NEXT_DATA__ or similar).
    We search for the first large JSON block and walk it for lot-like dicts.
    """
    lots: list[RawListing] = []

    # __NEXT_DATA__ pattern
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>\s*(\{.*?\})\s*</script>', html, re.S)
    blobs: list[str] = []
    if m:
        blobs.append(m.group(1))
    else:
        # fallback: the largest <script type="application/json"> blob
        for sm in re.finditer(r'<script[^>]+application/json"[^>]*>\s*(\{.*?\})\s*</script>', html, re.S):
            blobs.append(sm.group(1))

    seen_ids = set()
    for raw in blobs:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        # Walk the JSON and pick objects that look like a "lot"
        candidates: list[dict[str, Any]] = []
        _walk_json_for_lots(data, candidates)

        for obj in candidates:
            # title/name
            title = (
                obj.get("title")
                or obj.get("name")
                or obj.get("lotTitle")
                or obj.get("lotName")
            )
            if not title:
                continue

            # url / slug / id
            url = (
                obj.get("url")
                or obj.get("href")
                or obj.get("lotUrl")
            )
            if url and url.startswith("/"):
                url = urljoin(base_url, url)
            if not url:
                slug = obj.get("slug") or obj.get("lotSlug")
                lot_id = obj.get("id") or obj.get("lotId") or obj.get("uuid")
                if slug:
                    url = urljoin(base_url, f"/en/lots/{slug}")
                elif lot_id:
                    url = urljoin(base_url, f"/en/lots/{lot_id}")
            if not url:
                continue

            # external id
            external_id = (
                obj.get("id")
                or obj.get("lotId")
                or obj.get("uuid")
                or url.strip("/").split("/")[-1]
            )
            if external_id in seen_ids:
                continue
            seen_ids.add(external_id)

            # image
            photo = (
                obj.get("image")
                or obj.get("imageUrl")
                or obj.get("thumbnailUrl")
                or obj.get("mainImageUrl")
                or _deep_get(obj, "image.src")
                or _deep_get(obj, "thumbnail.src")
            )

            # price
            price = (
                obj.get("price")
                or obj.get("currentPrice")
                or obj.get("biddingPrice")
                or _deep_get(obj, "currentPrice.amount")
                or _deep_get(obj, "current_price.amount")
                or _deep_get(obj, "price.amount")
                or _deep_get(obj, "price.value")
            )
            try:
                price_value = float(str(price).replace(",", "."))
            except Exception:
                price_value = 0.0

            lots.append(
                RawListing(
                    source="vavato",
                    external_id=str(external_id),
                    url=url,
                    title=str(title)[:180],
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

    return lots

def _walk_json_for_lots(node: Any, out: list[dict[str, Any]]):
    """Collect dicts that look like lot records."""
    if isinstance(node, dict):
        if ("lots" in node and isinstance(node["lots"], list)):
            for it in node["lots"]:
                if isinstance(it, dict):
                    out.append(it)
        # generic heuristic: dict with id + (title|name) + (image|thumbnail)
        if (
            ("id" in node or "uuid" in node or "lotId" in node)
            and ("title" in node or "name" in node or "lotTitle" in node)
            and any(k in node for k in ("image", "imageUrl", "thumbnailUrl", "mainImageUrl", "thumbnail"))
        ):
            out.append(node)
        for v in node.values():
            _walk_json_for_lots(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_json_for_lots(v, out)

def _deep_get(d: dict, path: str):
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def _parse_price(text: str | None) -> float:
    if not text:
        return 0.0
    cleaned = str(text).replace("\xa0", " ").replace(".", "").replace(",", ".")
    m = re.search(r"€\s*([0-9]+(?:\.[0-9]+)?)", cleaned)
    try:
        return float(m.group(1)) if m else 0.0
    except Exception:
        return 0.0
