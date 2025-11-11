# modules/scrapers.py
import html
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
        """Scrape all <li> papers in the 'Selected Articles' section with robust title extraction."""
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

        lis = ul.find_all("li")
        total_li = len(lis)
        missed = []
        extracted = 0

        for li in lis:
            a_tag = li.find("a", href=True)
            link = a_tag["href"].strip() if a_tag else None
            if link and link.startswith("/"):
                link = f"https://mechse.illinois.edu{link}"

            title = self._extract_paper_title(li)

            if title:
                papers.append({"title": title, "link": link})
                extracted += 1
            else:
                # Record original text for debugging
                raw_text = (li.get("aria-label") or li.get_text(" ", strip=True)).strip()
                missed.append({"raw": raw_text, "link": link})

        # Summary / debug printout
        print(f"  🧾 Found {len(papers)} titles from {total_li} list items on {profile_url}")
        if missed:
            print(f"  ⚠️ Missed {len(missed)} items — sample:")
            for m in missed[:6]:
                print("   -", (m["raw"][:180] + "...") if len(m["raw"]) > 180 else m["raw"])
        else:
            print("  ✅ Extracted all list items.")

        return papers
    
    def _extract_paper_title(self, li_tag):
        """
        Robust extractor for messy faculty <li> citations.
        Prints which stage matched when it's NOT stage 1 to help debugging.
        """
        import html
        import re
        from unicodedata import normalize

        def clean_text(s: str) -> str:
            s = html.unescape(s or "")
            s = normalize("NFKC", s)
            s = re.sub(r'[\u2018\u2019\u201C\u201D\u009D\u00AB\u00BB\uFF02\uFF07â€œâ€]', '"', s)
            s = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0Dâ€]', '-', s)
            s = re.sub(r'\s+', ' ', s).strip()
            s = re.sub(r'^[\s\-,;:\u201C\u201D\u2018\u2019\uFF0C\uFE10]+', '', s)
            s = re.sub(r'[\s\-,;:\u201C\u201D\u2018\u2019\uFF0C\uFE10]+$', '', s)
            s = re.sub(r'[â€œ”œ‰�]+', '', s)
            s = (s
                .replace("â€œ", "“")
                .replace("â€", "”")
                .replace("â€˜", "‘")
                .replace("â€™", "’")
                .replace("â€“", "–")
                .replace("â€”", "—")
                .replace("â€¦", "…"))
            # Also strip stray bytes that sometimes remain (â, �, etc.)
            s = re.sub(r'[â�]+', '', s)

            return s
        
        def strip_leading_punct(s: str) -> str:
            # remove leading whitespace and common punctuation including parentheses/brackets
            return re.sub(r'^[\s\-\–\—\:\.;,)\]\(\[\{\uFE10\uFF08\uFF09]+', '', s)


        def token_count(s: str) -> int:
            return len(re.findall(r"[A-Za-z0-9]+", s))

        def looks_like_author_fragment(s: str) -> bool:
            # Return True for strings that look like an author-list fragment, e.g.:
            # "Smith, J. A."  or "Smith, J., Jones, M." or many short initial-like tokens.
            if not s:
                return False

            # Normalize whitespace for reliable token checks
            s_n = re.sub(r'\s+', ' ', s).strip()

            # 1) If it starts with a surname-like token followed by a comma,
            #    but the token after the comma is a short token (initial or <=3 chars),
            #    treat as author. This avoids false-positives for titles like "Design, Dynamics..."
            m = re.match(r'^([A-Z][A-Za-z\-\']+(?:\s+[A-Z][A-Za-z\-\']+)*)\s*,\s*([^\s,]+)', s_n)
            if m:
                next_tok = m.group(2)
                # consider it an author fragment if the token after the comma is an initial
                # (single letter with optional dot) or a very short token (<=3 chars)
                if re.fullmatch(r'[A-Z]\.?', next_tok) or len(next_tok) <= 3:
                    return True
                # otherwise, likely it's a title phrase ("Design, Dynamics..."), so do not treat as author

            # 2) If there are many commas and the early tokens are short (initials)
            #    e.g. "Smith, J., Jones, M., Brown, A."
            tokens = re.findall(r"[A-Za-z0-9]+", s_n)
            if s_n.count(',') >= 2 and all(len(t) <= 3 for t in tokens[:4]):
                return True

            # 3) A final guard: if the string is mostly initials / single-letter tokens, treat as author fragment
            short_tokens = [t for t in tokens[:6] if len(t) <= 3]
            if len(short_tokens) >= max(2, min(4, len(tokens))):
                return True
            
            # 4) If it ends with "and <capital>" or "and <capital> <initial>", treat as author fragment
            if re.search(r'\band\s+[A-Z](?:[a-z]+\.?|(?:\s+[A-Z]\.?)?)$', s_n):
                return True

            return False


        def is_title_candidate(candidate: str, original: str, allow_author_like=False) -> bool:
            if not candidate:
                return False
            cand = candidate.strip().strip('".,;:')
            if len(cand) < 6:
                return False
            words = cand.split()
            if len(words) < 2:
                return False
            if not re.search(r'[A-Za-z]', cand):
                return False

            if not allow_author_like:
                # reject obvious author fragments
                if looks_like_author_fragment(cand):
                    return False
                # avoid returning things that look like repeated author lists
                if cand.count(',') >= 3 and re.search(r'\b(19|20)\d{2}\b', original or ""):
                    if cand.count(',') > 1:
                        return False
                # avoid DOI / URL / journal-only strings unless title-like (has lowercase words)
                if re.search(r'doi\.org|https?://|Journal|Proceedings|Vol\.|pp\.|\b\d{4}\b', cand, re.I):
                    if not re.search(r'[a-z]', cand) or len(words) < 4:
                        return False
                # reject kicker tokens (not part of a real title)
                if re.search(r'\b(arxiv|preprint|accepted|in press|submitted)\b', cand, re.I):
                    return False

            # reject trailing "(2024)" etc
            if re.fullmatch(r'\(?\d{4}\)?', cand):
                return False

            return True

        # Helper debug printer (only print if origin not stage1)
        def debug_report(stage: int, candidate: str, raw_text: str):
            try:
                print(f"  🔎 Title chosen by Stage {stage}: '{candidate[:140]}'")
                print(f"    raw preview: '{(raw_text[:160] + '...') if len(raw_text) > 160 else raw_text}'")
            except Exception:
                pass

        # Get raw text: prefer aria-label (full citation) else visible text
        raw = None
        try:
            raw = li_tag.get("aria-label") if (hasattr(li_tag, "get") and li_tag.get("aria-label")) else li_tag.get_text(" ", strip=True)
        except Exception:
            raw = str(li_tag)
        raw = clean_text(raw or "")
        if not raw:
            return None
        
        raw = re.sub(r'\*', '', raw)

        
        raw_text_for_stage1 = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)

        # --- Stage 1: QUOTED chunks (best first) ---
        quoted_matches = re.findall(
            r'(?:["“”\u201C\u201D]|&quot;)\s*([^"]+?)\s*(?=["“”\u201C\u201D]|&quot;)',
            raw_text_for_stage1
        )
        quoted_matches = [clean_text(q) for q in quoted_matches]
        if not quoted_matches:
            qstart = re.search(r'(?:["“”\u201C\u201D\u009D]|&quot;)', raw_text_for_stage1)
            if qstart:
                chunk = raw[qstart.end():]
                # Change 3: add more stop-words (accepted, arXiv, preprint, etc.)
                chunk = re.split(
                    r'(?:\bJournal\b|\bProceedings\b|\bInternational\b|\bVol\.?\b|\bpp\.?\b|\bdoi\.org\b|\b(arxiv|preprint|accepted|in press|submitted)\b|\b\d{4}\b)',
                    chunk, maxsplit=1
                )[0]
                quoted_matches = [chunk.strip()]
        if quoted_matches:
            # Stage 1 titles are allowed to look like author fragments
            for q in sorted(quoted_matches, key=lambda s: -token_count(s)):
                q_clean = clean_text(q)
                if token_count(q_clean) >= 2 and is_title_candidate(q_clean, raw, allow_author_like=True):
                    return q_clean

        # --- Stage 2: AFTER YEAR (YYYY) -> take remainder as title candidate ---
                # --- Stage 2: AFTER YEAR (YYYY) -> take remainder as title candidate ---
        ym = re.search(r'\b(19|20)\d{2}\b', raw)
        if ym:
            after_year = raw[ym.end():].strip()
            # drop leading punctuation/connector
            after_year = strip_leading_punct(after_year)


            # cut off obvious journal/kicker parts (expanded to include arXiv/preprint/accepted/in press/submitted)
            after_year = re.split(
                r'(?:\bJournal\b|\bJ\.?\b|\bProceedings\b|\bProc\.?\b|\bInternational\b|\bIn:|\bVol\.?\b|\bpp\.?\b|'
                r'\barXiv\b|\bpreprint\b|\baccepted\b|\bin press\b|\bsubmitted\b)',
                after_year, maxsplit=1
            )[0]

            after_year = clean_text(after_year)

            # Reject obvious author fragments or kicker tokens like "arXiv" / "preprint" before accepting.
            if (not looks_like_author_fragment(after_year)
                    and not re.search(r'\b(arxiv|preprint|accepted|in press|submitted)\b', after_year, re.I)
                    and is_title_candidate(after_year, raw)):
                debug_report(2, after_year, raw)
                return after_year
            # otherwise continue to other heuristics (do not return here)

        # --- Stage 3: AUTHORS. TITLE, Journal --- extract between last author-period and journal marker
        # Strategy: split on the FIRST author-block terminating period, but protect against initial-only fragments.
        # match full author list
        author_match = re.match(
            r'^((?:[A-Z][a-zA-Z\-\.]+(?:\s+[A-Z][a-zA-Z\-\.]+)?(?:,|,?\s+and|,?\s+&)\s*)+[A-Z][a-zA-Z\-\.]+)[\.,]\s+',
            raw
        )

        if author_match:
            after_authors = raw[author_match.end():].strip()
            seg = re.split(
                r'(?:,?\s*(?:J\.|Journal|Proc\.|Proceedings|Int\.|International|Vol\.|pp\.|\d{4}|accepted|in press|submitted))',
                after_authors, maxsplit=1
            )[0]
            seg = clean_text(seg)
            # only accept if not an author fragment
            if not looks_like_author_fragment(seg) and is_title_candidate(seg, raw):
                debug_report(3, seg, raw)
                return seg


        # --- Stage 4: BEFORE <em> (journal tag) - get content up to <em> and strip authors conservatively ---
        try:
            em = li_tag.find("em")
            if em:
                parts = []
                for elem in li_tag.children:
                    if elem == em:
                        break
                    if isinstance(elem, str):
                        parts.append(elem)
                    else:
                        parts.append(elem.get_text(" ", strip=True))
                before_em = clean_text(" ".join(parts))
                ym2 = re.search(r'\b(19|20)\d{2}\b', before_em)
                if ym2:
                    cand = before_em[ym2.end():].strip()
                else:
                    p = before_em.find('.')
                    if 0 < p < 80:
                        cand = before_em[p+1:].strip()
                    else:
                        cand = re.sub(r'^(?:[A-Z][a-z]+(?:,|\s))*\s*', '', before_em, count=1).strip()
                cand = clean_text(cand)
                if not looks_like_author_fragment(cand) and is_title_candidate(cand, raw):
                    debug_report(4, cand, raw)
                    return cand
        except Exception:
            pass

        raw = re.sub(r'(?:,\s*and\s+[A-Z]\.?[A-Za-z]?|and\s+[A-Z]\.?[A-Za-z]?)$', '', raw)


        # --- Stage 5: conservative chunk fallback: pick best chunk from sentence-like splits ---
        pieces = re.split(r'\.\s+|\;\s+', raw)  # split on periods/semicolons
        candidates = []
        for p in pieces:
            p_clean = clean_text(p)
            if not p_clean:
                continue
            if looks_like_author_fragment(p_clean):
                continue
            if is_title_candidate(p_clean, raw):
                candidates.append(p_clean)

        if candidates:
            # Prefer longest reasonable one
            best = max(candidates, key=lambda s: (len(s.split()), len(s)))
            debug_report(5, best, raw)
            return best

        # --- Stage 6: final fallback try: pick longest segment with colon or long chunk ---
        colon_segments = [clean_text(s) for s in re.split(r'\s*[,:]\s*', raw) if s]
        colon_segments_sorted = sorted(colon_segments, key=lambda s: -len(s))
        for seg in colon_segments_sorted:
            if ':' in seg or '-' in seg or len(seg.split()) >= 4:
                if not looks_like_author_fragment(seg) and is_title_candidate(seg, raw):
                    debug_report(6, seg, raw)
                    return seg

        return None



        
    






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
        """Scrape Northwestern professor's 'Selected Publications' — robust across ul/ol/p variations."""
        try:
            r = self.session.get(profile_url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠️ Failed to load {profile_url}: {e}")
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        papers = []

        # Find the Selected Publications heading (allow variants)
        section = soup.find(lambda tag: tag.name in ("h2", "h3") and tag.get_text(strip=True) and re.search(r'Select(ed|ions)?\s+Public', tag.get_text(), re.I))
        if not section:
            print(f"  ℹ️ No 'Selected Publications' section on {profile_url}")
            return papers

        base_domain = "https://www.mccormick.northwestern.edu"

        def is_probable_pub_list(list_tag):
            """Return True if list_tag (ul/ol) looks like a publications list."""
            lis = list_tag.find_all("li", recursive=False)
            if not lis:
                return False
            score = 0
            for li in lis[:12]:
                txt = li.get_text(" ", strip=True)
                if re.search(r'\b(19|20)\d{2}\b', txt):       # has a year
                    score += 2
                if li.find("em"):                            # journal usually in <em>
                    score += 2
                if re.search(r'\bdoi\b|https?://|doi\.org', txt, re.I):
                    score += 1
                if len(txt.split()) > 6:
                    score += 1
            # threshold: needs some signal
            return score >= 3

        # find the nearest UL/OL that looks like publications (search next siblings and children)
        candidate_list = None
        # a few places to look: next siblings up to N, and inside the next few siblings
        checked = 0
        for sib in section.find_next_siblings(limit=12):
            if not getattr(sib, "name", None):
                continue
            if sib.name in ("ul", "ol") and is_probable_pub_list(sib):
                candidate_list = sib
                break
            # if it's a container that includes a suitable list
            found = sib.find(["ul", "ol"])
            if found and is_probable_pub_list(found):
                candidate_list = found
                break
            checked += 1
            if checked > 10:
                break

        # As a last resort, look for the first ul/ol after the heading (but validate)
        if candidate_list is None:
            first_list = section.find_next(["ul", "ol"])
            if first_list and is_probable_pub_list(first_list):
                candidate_list = first_list

        # If we found a list, parse it. Otherwise fall back to p blocks like before.
        def resolve_link(href):
            if not href:
                return None
            href = href.strip()
            if href.startswith("/"):
                return f"{base_domain}{href}"
            return href

        def nav_like_text(txt):
            # filter out obvious nav/promotional items
            return bool(re.search(r'\b(Faculty\s+Directory|Give to McCormick|Donate|Alumni|Research Faculty Directory|Directory|Faculty Profiles)\b', txt, re.I))

        if candidate_list:
            for li in candidate_list.find_all("li"):
                raw_txt = li.get_text(" ", strip=True)
                if not raw_txt or nav_like_text(raw_txt):
                    # skip nav-like or tiny lines
                    continue

                # prefer <em> content (journal/title) when present
                em = li.find("em")
                if em:
                    title = em.get_text(" ", strip=True)
                else:
                    # pass the Tag itself (so _extract_paper_title can use aria-label etc.)
                    title = self._extract_paper_title(li)

                # get a DOI/extern link if present (prefer DOI or external over internal nav links)
                link = None
                # prefer DOIs or known article hosts; but fallback to any a[href]
                a_tags = li.find_all("a", href=True)
                doi_link = None
                ext_link = None
                for a in a_tags:
                    href = a["href"].strip()
                    if re.search(r'doi\.org|dx\.doi\.org|10\.\d{4,9}/', href, re.I):
                        doi_link = href
                        break
                    if href.startswith("http"):
                        ext_link = href
                link = doi_link or ext_link or (a_tags[0]["href"].strip() if a_tags else None)
                link = resolve_link(link)

                if title:
                    papers.append({"title": title, "link": link})
        else:
            # fallback: scan following sibling <p> blocks until the next section header
            p_tags = []
            next_el = section.find_next_sibling()
            while next_el and getattr(next_el, "name", None) and next_el.name not in ["h2", "h3", "h4"]:
                if next_el.name == "p" and next_el.get_text(strip=True):
                    p_tags.append(next_el)
                next_el = next_el.find_next_sibling()

            for p in p_tags:
                raw_txt = p.get_text(" ", strip=True)
                if not raw_txt or nav_like_text(raw_txt):
                    continue

                # 1️⃣ Try to extract title inside quotes (double or single)
                match = re.search(r'["“](.+?)["”]', raw_txt)
                if match:
                    title = match.group(1).strip()
                else:
                    # 2️⃣ fallback: <em> content (journal), only if no quoted title
                    em = p.find("em")
                    if em:
                        title = em.get_text(" ", strip=True)
                    else:
                        # 3️⃣ fallback: use your old extractor as last resort
                        title = self._extract_paper_title(p)

                a_tag = p.find("a", href=True)
                link = resolve_link(a_tag["href"]) if a_tag else None

                if title:
                    papers.append({"title": title, "link": link})


        print(f"  🧾 Found {len(papers)} papers on {profile_url}")
        return papers
