# modules/indexer.py
import re
import json
import time
from pathlib import Path
from collections import Counter
from . import config
from .scholar_client import ScholarClient


class ScholarIndexer:
    """
    Builds/updates database.json using Semantic Scholar API.
    Reads professors.json (university/department -> [names]) and:
      1. Resolves each professor to a Semantic Scholar authorId
      2. Fetches their papers
      3. Builds a normalized DB with `professors` and `papers`
    """

    def __init__(self):
        self.client = ScholarClient(api_key=getattr(config, "S2_API_KEY", None))
        self.professors_path = Path(config.PROFESSORS_PATH)
        self.db_path = Path(config.BASE_PATH) / "database.json"

    # ---------- File IO ----------

    def _load_professors_hier(self):
        """Load hierarchical professors.json"""
        if self.professors_path.exists():
            try:
                return json.loads(self.professors_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Error reading professors.json: {e}")
                return {}
        return {}

    def _load_db(self):
        """Load database.json"""
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception:
                return {"professors": {}, "papers": {}}
        return {"professors": {}, "papers": {}}

    def _save_db(self, data):
        """Write database.json"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------- Core Helpers ----------
    def resolve_author_id_via_papers(self, name, papers, max_papers=5):
        """
        Try to find a stable authorId by looking up up to `max_papers` known paper titles.
        Returns the most frequent matching authorId across papers.

        Matching heuristic:
          - normalize names (lowercase, remove extra whitespace, remove punctuation)
          - compare last names exactly
          - then consider first-name initials or full-first-name presence as match:
              * first initials equal (e.g. "N." vs "Nikhil")
              * first token of scraped name appears in candidate name
              * candidate contains all initials from the scraped name (N C Admal -> N.C. Admal)
        """
        def name_parts(raw):
            """Return a dict with normalized last, first token, initials list."""
            if not raw:
                return {"last": "", "first": "", "initials": []}
            s = raw.replace("\u00a0", " ")  # NBSP
            s = s.strip()
            # If "Last, First ..." format, flip to "First Last"
            if "," in s:
                parts = [p.strip() for p in s.split(",") if p.strip()]
                if len(parts) >= 2:
                    s = parts[1] + " " + parts[0]
            # remove parentheses, quotes, extra punctuation except spaces and dots (keep dots for initials)
            s_clean = re.sub(r"[()\"'’„”“\[\]\-:;]", " ", s)
            s_clean = re.sub(r"\s+", " ", s_clean).strip()
            tokens = [t for t in re.split(r"[,\s]+", s_clean) if t]
            tokens = [t.strip(".") for t in tokens]  # remove trailing dots from initials/tokens
            if not tokens:
                return {"last": "", "first": "", "initials": []}
            last = tokens[-1].lower()
            first = tokens[0].lower()
            initials = [t[0].lower() for t in tokens if t]  # use first char of each token
            return {"last": last, "first": first, "initials": initials, "raw": s_clean.lower()}

        def name_matches(candidate_name, target_name):
            """
            Return True if candidate_name (from API) plausibly refers to target_name (scraped professor).
            """
            cand = name_parts(candidate_name)
            targ = name_parts(target_name)

            if not cand["last"] or not targ["last"]:
                return False

            # Last name must match exactly
            if cand["last"] != targ["last"]:
                return False

            # If exact raw substring match (e.g. full name present), accept
            if targ["raw"] in cand["raw"] or cand["raw"] in targ["raw"]:
                return True

            # Check first-initial match
            # e.g. target initials ['n','c'] and candidate initials ['n'] -> consider match
            if cand["initials"] and targ["initials"]:
                if cand["initials"][0] == targ["initials"][0]:
                    return True

            # Check if candidate contains the full first token of target:
            # target first = 'nikhil' candidate raw might be 'n admal' -> first won't be present;
            # but if candidate has 'nikhil admal' => matches above.
            if targ["first"] and targ["first"] in cand["raw"]:
                return True

            # Check if candidate initials include target's first initial
            if targ["initials"] and targ["initials"][0] in cand["initials"]:
                return True

            # Fallback: if candidate has only initial + last and target has same last, accept
            # (This helps match "N. Admal" with "Nikhil Admal")
            if len(cand["initials"]) == 1 and cand["raw"].startswith(cand["initials"][0]) and cand["last"] == targ["last"]:
                return True

            return False

        name_lower = name  # keep original for passing to matching helper
        author_hits = Counter()

        sample_papers = (papers or [])[:max_papers]

        for paper in sample_papers:
            title = paper.get("title")
            if not title:
                continue

            print(f"    Searching paper: {title[:80]}...")
            try:
                results = self.client.search_papers(title, limit=1, fields="title,authors,year,url,paperId")
            except Exception as e:
                print(f"      ⚠️ Error fetching '{title}': {e}")
                continue

            if not results:
                print("      No results found.")
                continue

            # Look for a matching author in any result
            for r in results:
                for a in r.get("authors", []):
                    if not isinstance(a, dict):
                        continue
                    cand_name = a.get("name", "")
                    cand_id = a.get("authorId")
                    if not cand_name or not cand_id:
                        continue
                    if name_matches(cand_name, name_lower):
                        author_hits[cand_id] += 1
                        print(f"      Matched candidate author '{cand_name}' -> {cand_id}")

        if not author_hits:
            print(f"    ❌ No authorId found for {name}")
            return None

        best_id, count = author_hits.most_common(1)[0]
        print(f"    ✅ Found authorId {best_id} for {name} (matched {count} paper(s))")
        return best_id



    def resolve_author_id(self, name, uni=None, dept=None, db=None):
        """Try to find or reuse an authorId for a given professor name."""
        # 1. Reuse existing
        if db:
            for aid, info in db.get("professors", {}).items():
                if info.get("name") == name:
                    return aid
        try:
            candidates = self.client.search_authors(name, limit=5)
            if not candidates:
                print(f"  No authorId found for {name}")
                return None
            if len(candidates) > 1:
                # Build error message
                msg_lines = [f"Multiple author candidates found for '{name}':"]
                for c in candidates:
                    msg_lines.append(
                        f"- {c.get('name')} ({c.get('authorId')}), "
                        f"Papers: {c.get('paperCount', 0)}, "
                        f"Citations: {c.get('citationCount', 0)}, "
                        f"URL: {c.get('url')}"
                    )
                msg = "\n".join(msg_lines)
                print(f"\n⚠️ {msg}\nSkipping adding to DB for now.\n")

                # Save to error.txt
                error_path = Path("error.txt")
                with error_path.open("a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n\n")

                return None
            return candidates[0].get("authorId")
        except Exception as e:
            print(f"  ERROR resolving authorId for {name}: {e}")
            return None

    def update_professor_papers(self, author_id, db, author_name=None):
        """Fetch and merge all papers for a given authorId, keeping authors as full objects."""
        paper_ids = set(db["professors"].get(author_id, {}).get("paperIds", []))

        try:
            papers = self.client.fetch_author_papers(author_id, limit=120)
        except Exception as e:
            print(f"  ERROR fetching papers for author {author_id}: {e}")
            return db, []

        if not papers:
            print("  No papers found.")
            return db, []

        for p in papers:
            pid = p.get("paperId")
            if not pid:
                continue

            existing = db["papers"].get(pid, {})

            # Merge author info: include the current professor as full object
            authors_list = existing.get("authors", [])
            authors_seen = {a.get("authorId") for a in authors_list if isinstance(a, dict)}

            if author_id not in authors_seen:
                authors_list.append({"authorId": author_id, "name": author_name or ""})

            # If paper metadata has other authors, merge them too
            if p.get("authors"):
                for a in p["authors"]:
                    if isinstance(a, dict) and a.get("authorId") not in authors_seen:
                        authors_list.append({"authorId": a.get("authorId"), "name": a.get("name")})
                        authors_seen.add(a.get("authorId"))

            merged = {
                "paperId": pid,
                "title": p.get("title") or existing.get("title"),
                "year": p.get("year") or existing.get("year"),
                "citations": p.get("citations") if p.get("citations") is not None else existing.get("citations"),
                "pdf_url": p.get("pdf_url") or existing.get("pdf_url"),
                "url": p.get("url") or existing.get("url"),
                "externalIds": p.get("externalIds") or existing.get("externalIds"),
                "venue": p.get("venue") or existing.get("venue"),
                "types": p.get("types") or existing.get("types"),
                "last_seen": time.strftime("%Y-%m-%d"),
                "authors": authors_list,
            }

            db["papers"][pid] = merged
            paper_ids.add(pid)

        print(f"  Linked {len(paper_ids)} papers for author {author_id}")
        return db, sorted(paper_ids)

    def upsert_professor(self, db, author_id, name, uni, dept, paper_ids):
        """Insert or update a professor record in DB"""
        db["professors"][author_id] = {
            "authorId": author_id,
            "name": name,
            "university": uni,
            "department": dept,
            "paperIds": paper_ids,
            "last_updated": time.strftime("%Y-%m-%d"),
        }
        return db

    # ---------- Main Orchestrator ----------

    def update_from_professors_file(self):
        hier = self._load_professors_hier()
        db = self._load_db()

        total = 0
        for uni, depts in hier.items():
            for dept, names in depts.items():
                for name, info in names.items():
                    papers = info.get("papers", [])

                    total += 1
                    print(f"\nProcessing {name}  ({uni} / {dept})")

                    author_id = self.resolve_author_id_via_papers(name, papers) or self.resolve_author_id(name, uni, dept, db)
                    if not author_id:
                        print(f"  Skipping {name} — no valid authorId found.")
                        continue

                    db, paper_ids = self.update_professor_papers(author_id, db, author_name=name)
                    db = self.upsert_professor(db, author_id, name, uni, dept, paper_ids)

                    self._save_db(db)
                    time.sleep(1.0)

        print(f"\n✅ Done. Processed {total} authors.")
        return db
