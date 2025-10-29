# modules/scholar_client.py
import time
import random
from typing import Optional, List
import requests

from . import config  # Use constants directly
from .utils import atomic_write_json  # Assuming you have this utility

S2_BASE = config.S2_BASE  # Use config constant

class RateLimiter:
    def __init__(self, min_interval: float = config.MIN_INTERVAL):
        self.min_interval = float(min_interval)
        self.last = 0.0

    def wait(self):
        now = time.time()
        delta = now - self.last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self.last = time.time()

class ScholarClient:
    def __init__(self, api_key: Optional[str] = None, limiter: Optional[RateLimiter] = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ScholarClient/1.0)"})
        if api_key:
            self.session.headers.update({"x-api-key": api_key})
        self.limiter = limiter or RateLimiter(config.MIN_INTERVAL)
        # Defaults for retry logic
        self.request_timeout = getattr(config, "REQUEST_TIMEOUT", 45)  # seconds
        self.default_limit = getattr(config, "DEFAULT_PAPER_LIMIT", 80)

    def _retry_get(self, url: str, params: dict = None, tries: int = 6, base_sleep: float = 1.5):
        for i in range(tries):
            self.limiter.wait()
            try:
                r = self.session.get(url, params=params, timeout=self.request_timeout)
            except requests.RequestException:
                r = None

            if r is not None and r.status_code == 200:
                return r

            status = r.status_code if r is not None else None
            if status in (429, 500, 502, 503, 504):
                retry_after = 0.0
                if r is not None:
                    ra = r.headers.get("Retry-After")
                    if ra:
                        try:
                            retry_after = float(ra)
                        except Exception:
                            retry_after = 0.0
                sleep_s = retry_after if retry_after > 0 else (base_sleep * (2 ** i))
                sleep_s += random.uniform(0.2, 1.0)
                time.sleep(sleep_s)
                continue
            break
        return None

    def search_authors(self, name: str, limit: int = 5) -> list:
        """
        Search Semantic Scholar for authors by name and return the raw candidate list.
        This does NOT pick one automatically.
        """
        url = f"{S2_BASE}/author/search"
        params = {"query": name, "limit": limit, "fields": "authorId,name,affiliations,url,paperCount,citationCount"}
        r = self._retry_get(url, params=params)
        if not r:
            return []
        data = r.json()
        return data.get("data", [])

    def fetch_author_papers(self, author_id: str, limit: int = None) -> List[dict]:
        limit = limit or self.default_limit
        url = f"{S2_BASE}/author/{author_id}/papers"
        params = {
            "limit": limit,
            "fields": ",".join([
                "paperId", "title", "year", "citationCount",
                "openAccessPdf", "isOpenAccess", "url",
                "externalIds", "venue", "publicationTypes",
                "authors"
            ])
        }
        r = self._retry_get(url, params=params)
        if not r:
            return []
        data = r.json()
        items = data.get("data", [])
        out = []

        for it in items:
            paper = it.get("paper") if "paper" in it else it
            if not paper:
                continue

            # --- Primary PDF (direct from API) ---
            pdf = None
            oap = paper.get("openAccessPdf")
            if isinstance(oap, dict) and oap.get("url"):
                pdf = oap["url"]

            # --- Fallback logic for missing PDFs ---
            if not pdf:
                ext = paper.get("externalIds") or {}
                if "ArXiv" in ext:
                    pdf = f"https://arxiv.org/pdf/{ext['ArXiv']}.pdf"
                elif "DOI" in ext:
                    pdf = f"https://doi.org/{ext['DOI']}"

            authors_list = []
            for a in paper.get("authors", []):
                if isinstance(a, dict):
                    authors_list.append({
                        "authorId": a.get("authorId"),
                        "name": a.get("name")
                    })

            # --- Collect all useful metadata for debugging ---
            out.append({
                "paperId": paper.get("paperId"),
                "title": paper.get("title"),
                "year": paper.get("year") or 0,
                "citations": paper.get("citationCount", 0) or 0,
                "pdf_url": pdf,
                "is_open_access": paper.get("isOpenAccess"),
                "venue": paper.get("venue"),
                "types": paper.get("publicationTypes"),
                "url": paper.get("url"),
                "externalIds": paper.get("externalIds") or {},
                "authors": authors_list
            })

        return out