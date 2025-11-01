# modules/scholar_client.py
import time
import random
from typing import Optional, List
import requests

from . import config  # Use constants directly
from .utils import atomic_write_json  # Assuming you have this utility

S2_BASE = config.S2_BASE  # Use config constant

class RateLimiter:
    def __init__(self, min_interval: float = 0.8, max_interval: float = 2):
        """Adaptive rate limiter: starts fast, gently backs off on 429s."""
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.dynamic_interval = min_interval
        self.last = 0.0

    def wait(self):
        now = time.time()
        delta = now - self.last
        if delta < self.dynamic_interval:
            time.sleep(self.dynamic_interval - delta)
        self.last = time.time()

    def backoff(self, factor: float = 1.2):
        """Increase delay slightly, up to max_interval."""
        self.dynamic_interval = min(self.max_interval, self.dynamic_interval * factor)
        print(f"🔄 Backoff: interval={self.dynamic_interval:.2f}s")

    def relax(self, factor: float = 0.85):
        """Slowly return to faster speed after successful call."""
        old_interval = self.dynamic_interval
        self.dynamic_interval = max(self.min_interval, self.dynamic_interval * factor)
        if abs(self.dynamic_interval - old_interval) > 1e-3:
            print(f"✅ Relax: interval={self.dynamic_interval:.2f}s")

    def reset(self):
        """Force reset to base interval (e.g., at startup)."""
        self.dynamic_interval = self.min_interval

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

    def _retry_get(self, url: str, params: dict = None, tries: int = 10):
        self.limiter.reset()
        for i in range(tries):
            self.limiter.wait()
            try:
                r = self.session.get(url, params=params, timeout=self.request_timeout)
            except requests.RequestException:
                r = None
            if r is not None and r.status_code == 200:
                self.limiter.relax()
                return r
            status = r.status_code if r is not None else None
            if status == 429:
                print(f"⚠️ 429 Too Many Requests (attempt {i+1})")
                self.limiter.backoff()
                retry_after = 0.0
                if r is not None and "Retry-After" in r.headers:
                    try:
                        retry_after = float(r.headers["Retry-After"])
                    except Exception:
                        retry_after = 0.0
                wait = max(self.limiter.dynamic_interval, retry_after or 0.3)
                wait = min(wait, 2)  # hard cap at 3s total wait
                print(f"   waiting {wait:.1f}s before retrying...")
                time.sleep(wait)
                continue
            elif status in (500, 502, 503, 504):
                time.sleep(min(2, 0.8 * (i + 1)))  # cap server errors too
                continue
            if i < tries - 1:
                print(f"⚠️ Unexpected status {status}, retrying ({i+1}/{tries})...")
                time.sleep(0.3)
                continue
            else:
                print(f"❌ Giving up after {tries} attempts (status {status})")

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
    
    def search_papers(self, query, limit=3, fields=None):
        """
        Search Semantic Scholar for papers matching the title/query.
        Returns a list of paper dicts with authors, paperId, title, etc.
        """
        # Example for S2 API v1
        print("making request for paper data")
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": fields or "title,authors,paperId",
        }
        r = self._retry_get(url, params=params)
        print("got paper data")
        print(r)
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