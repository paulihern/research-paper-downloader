# modules/scrapers_copy.py
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
    # HELPER: Filter top papers
    # ----------------------------------------
    def _filter_top_papers(self, papers, top_n=10):
        """
        Keep only top 10 most recent + top 10 most cited papers.
        Papers should have 'year' and 'citations' fields (can be None/0).
        Returns a deduplicated list of papers.
        """
        if not papers:
            return []
        
        # Sort by year (most recent first)
        by_year = sorted(papers, key=lambda p: p.get('year') or 0, reverse=True)
        top_recent = by_year[:top_n]
        
        # Sort by citations (most cited first)
        by_cites = sorted(papers, key=lambda p: p.get('citations') or 0, reverse=True)
        top_cited = by_cites[:top_n]
        
        # Combine and deduplicate by title
        combined = {}
        for p in top_recent + top_cited:
            title = p.get('title', '').strip()
            if title and title not in combined:
                combined[title] = p
        
        return list(combined.values())

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
    # STEP 2 — SCRAPE EACH PROFESSOR'S PAPERS
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
            
            # ✅ Filter to top 10 recent + top 10 cited
            filtered = self._filter_top_papers(papers, top_n=10)
            prof["papers"] = filtered
            
            self._save()  # ✅ save after every professor
            print(f"  Saved {len(filtered)} papers for {name} (filtered from {len(papers)})")
            time.sleep(1.0)

        print("\n✅ Done updating UIUC professor papers.")

    def _scrape_uiuc_professor_papers(self, profile_url):
        """Scrape all <li> papers in the 'Selected Articles' section."""
        try:
            r = self.session.get(profile_url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠️ Failed to load {profile_url}: {e}")
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        papers = []

        # Find the section
        section = soup.find("h2", string=lambda t: t and "Selected Article" in t)
        if not section:
            print(f"  ℹ️ No 'Selected Articles' section on {profile_url}")
            return papers

        ul = section.find_next("ul")
        if not ul:
            print(f"  ℹ️ No <ul> after section on {profile_url}")
            return papers

        for li in ul.find_all("li"):
            a_tag = li.find("a", href=True)
            link = a_tag["href"].strip() if a_tag else None
            if link and link.startswith("/"):
                link = f"https://mechse.illinois.edu{link}"

            # Pass the <li> tag to extract title (handles aria-label or quotes)
            title = self._extract_paper_title(li)

            if title:
                # Extract year and citations if available (basic regex)
                text = li.get_text(" ", strip=True)
                year = self._extract_year(text)
                citations = 0  # Not available from UIUC pages
                
                papers.append({
                    "title": title, 
                    "link": link,
                    "year": year,
                    "citations": citations
                })

        print(f"  🧾 Found {len(papers)} papers on {profile_url}")
        return papers

    def _extract_year(self, text):
        """Extract 4-digit year from citation text."""
        match = re.search(r'\b(19|20)\d{2}\b', text)
        return int(match.group(0)) if match else None

    def _parse_paper_li(self, li):
        # Extract link if exists
        a_tag = li.find("a", href=True) if hasattr(li, "find") else None
        link = a_tag["href"].strip() if a_tag else None
        if link and link.startswith("/"):
            link = f"https://mechse.illinois.edu{link}"

        # Extract title
        title = None
        if hasattr(li, "get") and li.get("aria-label"):
            title = self._extract_paper_title(li)
        else:
            title = self._extract_paper_title(li.get_text(" ", strip=True) if hasattr(li, "get_text") else str(li))

        if title:
            return {"title": title, "link": link}
        return None

    
    def _extract_paper_title(self, li_tag):
        """
        Extracts the paper title from a <li> or a string of citation text.
        """
        import html
        # If it's a BeautifulSoup tag, try aria-label
        if hasattr(li_tag, "get"):
            citation_text = li_tag.get("aria-label") or li_tag.get_text(" ", strip=True)
        else:
            citation_text = str(li_tag)
        citation_text = html.unescape(citation_text)
        
        # Step 1: try quoted titles
        match = re.search(r'[""](.+?)[""](?=[^""]*$)', citation_text)
        if match:
            title = match.group(1).strip()
            if len(title) > 5:
                return title

        # Step 2: fallback — remove leading authors
        text = re.sub(r"^(?:[A-Z]\.[A-Z\.]*\s*[A-Z][a-z]+(?:,| and|\s))+","", citation_text)
        text = re.split(r"(?:,?\s*\d{4})|(?:,?\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)*,?)", text)[0]
        text = re.sub(r"\s+", " ", text).strip()

        return text if len(text) > 5 else None

    def _extract_paper_title_from_citation(self, citation_text):
        if not citation_text:
            return None

        import html
        citation_text = html.unescape(citation_text)  # decode &quot;, &amp;, etc.

        # Step 1: Capture quoted title (curly or straight quotes)
        match = re.search(r'[""](.+?)[""]', citation_text)
        if match:
            return match.group(1).strip()

        # Step 2: Remove leading authors (initials + last names)
        fallback = re.sub(r'^.*?\d{4}\.\s*', '', citation_text)

        # Step 3: Remove trailing journal info if needed
        fallback = re.split(r'(?:\.\s*[^\.]+\d{4})|(?:,?\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)*,?\s*\d{1,4})', fallback)[0]

        return fallback.strip() if len(fallback.strip()) > 5 else None


    
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
            
            # ✅ Filter to top 10 recent + top 10 cited
            filtered = self._filter_top_papers(papers, top_n=10)
            prof["papers"] = filtered
            
            self._save()
            print(f"  Saved {len(filtered)} papers for {name} (filtered from {len(papers)})")
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

                text = li.get_text(" ", strip=True)
                year = self._extract_year(text)
                
                if title:
                    papers.append({
                        "title": title, 
                        "link": link,
                        "year": year,
                        "citations": 0
                    })

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

                year = self._extract_year(text)

                if title:
                    papers.append({
                        "title": title, 
                        "link": link,
                        "year": year,
                        "citations": 0
                    })

        print(f"  🧾 Found {len(papers)} papers on {profile_url}")
        return papers