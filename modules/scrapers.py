# modules/scrapers.py
import re
import json
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from . import config

class FacultyScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; FacultyScraper/2.0)"
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

    # ----------------------------------------
    # STEP 1 — SCRAPE DIRECTORY
    # ----------------------------------------
    def update_uiuc_directory(self):
        base_url = "https://mechse.illinois.edu"
        list_url = f"{base_url}/people/faculty"
        print(f"Scraping faculty list from {list_url}")

        r = self.session.get(list_url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        self.data.setdefault("UIUC", {})
        self.data["UIUC"].setdefault("Mechanical Engineering", {})

        existing = self.data["UIUC"]["Mechanical Engineering"]
        added = 0

        for item in soup.select("div.item.person"):
            name_tag = item.select_one("div.details div.name a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            href = name_tag.get("href")
            if not href:
                continue

            profile_url = base_url + href
            prof_data = existing.get(name, {})
            prof_data["profile_url"] = profile_url
            prof_data.setdefault("papers", [])

            if name not in existing:
                print(f"🆕 Added: {name}")
                added += 1

            existing[name] = prof_data

        self.data["UIUC"]["Mechanical Engineering"] = existing
        self._save()
        print(f"✅ Saved directory. Added {added} new professors.")

    # ----------------------------------------
    # STEP 2 — SCRAPE EACH PROFESSOR’S PAPERS
    # ----------------------------------------
    def update_uiuc_professor_papers(self):
        """Iterate over saved professors, fetch their papers, and save after each."""
        base = self.data.get("UIUC", {}).get("Mechanical Engineering", {})
        if not base:
            print("⚠️ No UIUC professors found. Run update_uiuc_directory() first.")
            return

        for name, prof in base.items():
            url = prof.get("profile_url")
            if not url:
                continue

            print(f"\n📘 Fetching papers for {name}")
            papers = self._scrape_uiuc_professor_papers(url)
            prof["papers"] = papers
            self._save()  # ✅ save after every professor
            print(f"  Saved {len(papers)} papers for {name}")
            time.sleep(1.0)

        print("\n✅ Done updating UIUC professor papers.")

    def _scrape_uiuc_professor_papers(self, profile_url):
        """Scrape one UIUC professor's profile page for papers (handles linked + unlinked)."""
        try:
            r = self.session.get(profile_url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠️ Failed to load {profile_url}: {e}")
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        papers = []

        # Find section header — can be "Selected Articles", "Selected Articles in Journals", etc.
        section = soup.find("h2", string=lambda t: t and "Selected Article" in t)
        if not section:
            print(f"  ℹ️ No 'Selected Articles' section on {profile_url}")
            return papers

        ul = section.find_next("ul")
        if not ul:
            print(f"  ℹ️ No <ul> found after section on {profile_url}")
            return papers

        for li in ul.find_all("li"):
            a_tag = li.find("a", href=True)
            full_text = li.get_text(" ", strip=True)
            link = a_tag["href"].strip() if a_tag else None
            if link and link.startswith("/"):
                link = f"https://mechse.illinois.edu{link}"

            title = self._extract_paper_title(full_text)
            if title:
                papers.append({"title": title, "link": link})

        print(f"  🧾 Found {len(papers)} papers on {profile_url}")
        return papers
    
    def _extract_paper_title(self, citation_text):
        """
        Extract only the paper title from a full citation string.
        Example:
        Input:  'O.E. Orsel, J. Noh, ... "Giant non-reciprocity..." Physical Review Letters, 2025.'
        Output: 'Giant non-reciprocity and gyration through modulation-induced Hatano-Nelson coupling in integrated photonics'
        """
        # --- Case 1: Quoted title (most common)
        match = re.search(r"[\"“](.*?)[\"”]", citation_text)
        if match:
            return match.group(1).strip()

        # --- Case 2: No quotes → heuristic fallback
        # Remove author prefixes (initials and commas)
        text = re.sub(r"^(?:[A-Z]\.[A-Z\.]*\s*[A-Z][a-z]+(?:,| and|\s))+", "", citation_text)
        # Stop before journal keywords
        text = re.split(r",\s*(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)*|\d{4})", text)[0].strip()
        # Capitalize properly
        text = re.sub(r"\s+", " ", text)
        return text if len(text) > 5 else None
    
    # ----------------------------------------
    # NORTHWESTERN UNIVERSITY — DIRECTORY
    # ----------------------------------------
    def update_northwestern_directory(self):
        base_url = "https://www.mccormick.northwestern.edu"
        list_url = f"{base_url}/mechanical/people/faculty/"
        print(f"Scraping faculty list from {list_url}")

        try:
            r = self.session.get(list_url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"⚠️ Failed to fetch Northwestern faculty list: {e}")
            return

        soup = BeautifulSoup(r.content, "html.parser")

        self.data.setdefault("Northwestern", {})
        self.data["Northwestern"].setdefault("Mechanical Engineering", {})

        existing = self.data["Northwestern"]["Mechanical Engineering"]
        added = 0

        for div in soup.select("div.faculty.cf"):
            name_tag = div.select_one("div.faculty-info h3 a")
            if not name_tag:
                continue
            name = name_tag.get_text(" ", strip=True)
            href = name_tag.get("href")
            if not href:
                continue

            profile_url = href if href.startswith("http") else f"{base_url}{href}"
            prof_data = existing.get(name, {})
            prof_data["profile_url"] = profile_url
            prof_data.setdefault("papers", [])

            if name not in existing:
                print(f"🆕 Added: {name}")
                added += 1

            existing[name] = prof_data

        self.data["Northwestern"]["Mechanical Engineering"] = existing
        self._save()
        print(f"✅ Saved Northwestern directory. Added {added} new professors.")


    # ----------------------------------------
    # NORTHWESTERN UNIVERSITY — PROFESSOR PAPERS
    # ----------------------------------------
    def update_northwestern_professor_papers(self):
        base = self.data.get("Northwestern", {}).get("Mechanical Engineering", {})
        if not base:
            print("⚠️ No Northwestern professors found. Run update_northwestern_directory() first.")
            return

        for name, prof in base.items():
            url = prof.get("profile_url")
            if not url:
                continue

            print(f"\n📘 Fetching papers for {name}")
            papers = self._scrape_northwestern_professor_papers(url)
            prof["papers"] = papers
            self._save()
            print(f"  Saved {len(papers)} papers for {name}")
            time.sleep(1.0)

        print("\n✅ Done updating Northwestern professor papers.")


    def _scrape_northwestern_professor_papers(self, profile_url):
        """Scrape Northwestern professor's 'Selected Publications' — supports <ul><li> and <p> structures with or without <em>."""
        try:
            r = self.session.get(profile_url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠️ Failed to load {profile_url}: {e}")
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        papers = []

        # Find the section
        section = soup.find("h2", string=lambda t: t and "Selected Publication" in t)
        if not section:
            print(f"  ℹ️ No 'Selected Publications' section on {profile_url}")
            return papers

        # --- CASE 1: <ul><li> structure ---
        ul = section.find_next("ul")
        if ul and ul.find_all("li"):
            for li in ul.find_all("li"):
                em = li.find("em")
                title = em.get_text(" ", strip=True) if em else None
                if not title:
                    # fallback if no <em> — use regex to extract quoted titles
                    title = self._extract_paper_title(li.get_text(" ", strip=True))

                link = None
                a_tag = li.find("a", href=True)
                if a_tag:
                    link = a_tag["href"].strip()
                    if link.startswith("/"):
                        link = f"https://www.mccormick.northwestern.edu{link}"

                if title:
                    papers.append({"title": title, "link": link})

        else:
            # --- CASE 2: <p> structure (with or without <em>) ---
            p_tags = []
            next_el = section.find_next_sibling()
            while next_el and next_el.name and next_el.name not in ["h2", "h3", "h4"]:
                if next_el.name == "p" and next_el.get_text(strip=True):
                    p_tags.append(next_el)
                next_el = next_el.find_next_sibling()

            for p in p_tags:
                text = p.get_text(" ", strip=True)
                if not text or len(text) < 10:
                    continue

                em = p.find("em")
                title = em.get_text(" ", strip=True) if em else None

                if not title:
                    # fallback — extract quoted or capitalized title from text
                    title = self._extract_paper_title(text)

                link = None
                a_tag = p.find("a", href=True)
                if a_tag:
                    link = a_tag["href"].strip()
                    if link.startswith("/"):
                        link = f"https://www.mccormick.northwestern.edu{link}"

                if title:
                    papers.append({"title": title, "link": link})

        print(f"  🧾 Found {len(papers)} papers on {profile_url}")
        return papers
