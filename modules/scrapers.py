# modules/scrapers.py
import json
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from . import config

class FacultyScraper:
    """
    Scrape faculty names (tight selectors) and persist a hierarchical professors.json:
      { "UIUC": { "Mechanical Engineering": ["Name A", "Name B"] }, "NU": { ... } }
    The scraper acts as an updater: adds only new names and prints new additions.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; FacultyScraper/1.0)"
        })
        self.path = Path(config.PROFESSORS_PATH)
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- UIUC scraper: tight selector for real people ---
    def _scrape_uiuc(self):
        url = "https://mechse.illinois.edu/people/faculty"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        names = []
        # Select element blocks representing people
        for item in soup.select("div.item.person"):
            name_tag = item.select_one("div.details div.name a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if name and len(name) > 2:
                names.append(name)
        return names

    # --- Northwestern scraper: tight selector (adjust if page layout differs) ---
    def _scrape_nu(self):
        url = "https://www.mccormick.northwestern.edu/mechanical/people/faculty/"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        names = []
        for item in soup.select("div.person, div.profile, li.faculty, div.faculty-list-item"):
            # try common nested name selectors
            name_tag = item.select_one("h3 a, h3, .name a, .name")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if name and len(name) > 2:
                names.append(name)
        if not names:
            for h in soup.select("h3"):
                nm = h.get_text(strip=True)
                if nm and len(nm) > 2:
                    names.append(nm)
        uniq = []
        seen = set()
        for n in names:
            if n not in seen:
                uniq.append(n); seen.add(n)
        return uniq

    def update_professors(self):
        """
        Scrape both sources and merge into hierarchical structure:
        { university: { department: [names...] } }
        Only adds newly discovered names, prints new ones.
        """
        print("Scraping faculty lists...")
        # prepare structure defaults
        if "UIUC" not in self.data:
            self.data["UIUC"] = {}
        if "NU" not in self.data:
            self.data["NU"] = {}

        uiuc_dept = "Mechanical Engineering"
        nu_dept = "Mechanical Engineering"

        existing_uiuc = set(self.data.get("UIUC", {}).get(uiuc_dept, []))
        existing_nu = set(self.data.get("NU", {}).get(nu_dept, []))

        # Scrape
        uiuc_names = self._scrape_uiuc()
        nu_names = self._scrape_nu()

        added = 0
        # merge UIUC
        for name in uiuc_names:
            if name not in existing_uiuc:
                existing_uiuc.add(name)
                print(f"Added new professor (UIUC): {name}")
                added += 1
        # merge NU
        for name in nu_names:
            if name not in existing_nu:
                existing_nu.add(name)
                print(f"Added new professor (NU): {name}")
                added += 1

        # commit back into hierarchical dict
        self.data["UIUC"].setdefault(uiuc_dept, [])
        self.data["UIUC"][uiuc_dept] = sorted(existing_uiuc)

        self.data["NU"].setdefault(nu_dept, [])
        self.data["NU"][nu_dept] = sorted(existing_nu)

        if added == 0:
            print("No new professors found. List is up to date.")
        else:
            print(f"Added {added} new professors.")

        # save file
        self._save()
        return self.data

    def get_professors(self):
        """Return hierarchical professors dict (no scraping)."""
        return self.data
