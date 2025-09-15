# app/scrapers/base.py
import httpx
from bs4 import BeautifulSoup  # noqa: F401
from typing import List
from app.schemas import RawListing

class BaseScraper:
    source = "base"
    base_url = ""

    async def fetch_text(self, url: str, timeout=20) -> str:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent":"Mozilla/5.0 (compatible; ELR/0.1)"}) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text

    async def search(self, keywords: list[str]) -> List[RawListing]:
        raise NotImplementedError
