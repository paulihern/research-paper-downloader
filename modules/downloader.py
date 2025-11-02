import os
import json
import shutil
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

#comment
#comment2
from .config import CONFIG
from .utils import atomic_write_json, make_tempfile
from .scholar_client import RateLimiter

class PaperDownloader:
    def __init__(self, metadata_path: Optional[str] = None, base_dir: Optional[Path] = None, workers: int = 4, limiter: Optional[RateLimiter] = None):
        self.metadata_path = metadata_path or str(CONFIG.metadata_path)
        self.base_dir = base_dir or CONFIG.base_dir
        self.workers = workers
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; PaperDownloader/1.0)"})
        self.lock = threading.Lock()
        self.limiter = limiter or RateLimiter(CONFIG.min_interval)
        self._load_metadata()

    def _load_metadata(self):
        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.meta = json.load(f)
        else:
            raise FileNotFoundError(f"Metadata file not found at {self.metadata_path}")

    def _persist(self):
        atomic_write_json(Path(self.metadata_path), self.meta)

    def _paper_save_path(self, professor_name: str, uni: str, paper_meta: dict) -> Path:
        # keep filename safe: allow alnum, space, underscore, dash
        safe_prof = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in professor_name).strip().replace(" ", "_")
        year = paper_meta.get("year") or 0
        cites = paper_meta.get("citations") or 0
        # use raw string here so backslashes/quotes don't produce SyntaxWarning
        forbidden = r'\/?:"<>|'
        title_snip = (paper_meta.get("title") or "").translate(str.maketrans('', '', forbidden)).strip()[:60]
        fname = f"{year}_{cites}c_{title_snip}.pdf"
        prof_dir = Path(self.base_dir) / uni / safe_prof
        prof_dir.mkdir(parents=True, exist_ok=True)
        return prof_dir / fname

    def download_missing(self, dry_run: bool = False):
        jobs = []
        for prof_name, prof_node in self.meta.get("professors", {}).items():
            uni = prof_node.get("university", "Unknown")
            for pid, p in prof_node.get("papers", {}).items():
                if p.get("downloaded"):
                    continue
                if not p.get("pdf_url"):
                    continue
                path = self._paper_save_path(prof_name, uni, p)
                jobs.append((prof_name, uni, pid, p, path))

        if not jobs:
            print("No missing downloadable PDFs found.")
            return

        print(f"Preparing to download {len(jobs)} files with {self.workers} workers (dry_run={dry_run})")

        if dry_run:
            for j in jobs:
                prof_name, uni, pid, p, path = j
                print(prof_name, "->", path)
            return

        from requests import RequestException
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            future_to_job = {}
            for job in jobs:
                future = ex.submit(self._download_one, *job)
                future_to_job[future] = job

            for fut in as_completed(future_to_job):
                job = future_to_job[fut]
                prof_name, uni, pid, p, path = job
                try:
                    ok = fut.result()
                except Exception as e:
                    print(f"Download failed for {prof_name} / {p.get('title')[:40]}: {e}")
                    ok = False
                if ok:
                    print(f"Saved: {path}")
                    with self.lock:
                        node = self.meta["professors"].get(prof_name, {})
                        paper_node = node.get("papers", {}).get(pid)
                        if paper_node:
                            paper_node["downloaded"] = True
                            paper_node["path"] = str(path)
                    self._persist()

    def _download_one(self, prof_name: str, uni: str, pid: str, p: dict, path: Path) -> bool:
        self.limiter.wait()
        url = p.get("pdf_url")
        if not url:
            return False
        tmp_path = make_tempfile(suffix=".pdf")
        try:
            with self.session.get(url, stream=True, timeout=CONFIG.request_timeout) as r:
                if r.status_code != 200:
                    return False
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp_path, str(path))
            return True
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
