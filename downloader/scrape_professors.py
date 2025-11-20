# This script scrapes faculty information (name + title) from two university
# Mechanical Engineering department websites: UIUC and Northwestern.
# It extracts professor names using multiple heuristics, filters out non-professor
# entries, and saves the results into TXT file.

import requests, time, csv, re
from bs4 import BeautifulSoup

UIUC_URL = "https://mechse.illinois.edu/people/faculty"
NU_URL   = "https://www.mccormick.northwestern.edu/mechanical/people/faculty/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

PROF_RE = re.compile(r"\bprofessor\b", re.I)

def get_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s

def get_soup(session, url, retries=2, timeout=25):
    for i in range(retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return BeautifulSoup(r.content, "html.parser")
        except Exception:
            if i == retries:
                return None
            time.sleep(1.2)

def looks_like_name(name):
    if not name or len(name) < 4:
        return False
    bad_words = (
        "directory", "faculty", "people", "staff", "office",
        "research", "news", "events", "contact",
        "department", "engineering"
    )
    lower = name.lower()
    if any(b in lower for b in bad_words):
        return False
    words = [w for w in re.split(r"\s+", name) if w]
    if not (1 < len(words) <= 4):
        return False
    ok = sum(1 for w in words if re.match(r"[A-Z][A-Za-z\-\.']*$", w))
    return ok >= max(2, len(words)-1)

def extract_name(el):
    for tag in ("h2", "h3", "h4"):
        t = el.find(tag)
        if t:
            txt = t.get_text(strip=True)
            if looks_like_name(txt):
                return txt
    a = el.find("a")
    if a:
        t = (a.get("title") or a.get_text(" ", strip=True)).strip()
        if looks_like_name(t):
            return t
    return None

def extract_title(el):
    for sel in (".title", ".position", ".faculty-title", ".field--name-field-position",
                ".person-title", "p", "td", "span"):
        t = el.select_one(sel)
        if t:
            txt = t.get_text(" ", strip=True)
            if txt and PROF_RE.search(txt):
                return txt
    sib = el.find_next_sibling()
    if sib:
        for sel in (".title", ".position", "p", "td", "span"):
            t = sib.select_one(sel)
            if t:
                txt = t.get_text(" ", strip=True)
                if txt and PROF_RE.search(txt):
                    return txt
    text = " ".join(el.get_text(" ", strip=True).split())
    m = re.search(r"([A-Za-z, \-/&]+professor[ A-Za-z, \-/&]*)", text, re.I)
    return m.group(1).strip() if m else None

def scrape_faculty(session, url, university):
    soup = get_soup(session, url)
    if not soup:
        print(f"[WARN] Failed to load {university} page")
        return []

    containers = soup.find_all(["article", "li", "div", "tr"])
    results, seen = [], set()

    for el in containers:
        name = extract_name(el)
        if not name:
            continue
        title = extract_title(el) or ""
        if not PROF_RE.search(title):
            blob = " ".join(el.get_text(" ", strip=True).split())
            if not PROF_RE.search(blob):
                continue
        key = (university, name)
        if key in seen:
            continue
        seen.add(key)
        results.append({"university": university, "name": name, "title": title})
    return results

def save_results(rows, names_path="name_screped.txt"):
    rows = sorted(rows, key=lambda r: (r["university"], r["name"]))
    uiuc = [r["name"] for r in rows if r["university"] == "UIUC"]
    nu   = [r["name"] for r in rows if r["university"] == "NU"]
    with open(names_path, "w", encoding="utf-8") as f:
        f.write("# UIUC\n")
        for n in uiuc: f.write(n + "\n")
        f.write("\n# NU\n")
        for n in nu: f.write(n + "\n")
    return uiuc, nu

def main():
    s = get_session()
    uiuc = scrape_faculty(s, UIUC_URL, "UIUC")
    nu   = scrape_faculty(s, NU_URL, "NU")
    all_rows = uiuc + nu
    uiuc_names, nu_names = save_results(all_rows)

    print(f"UIUC: {len(uiuc_names)} | NU: {len(nu_names)} | Total: {len(all_rows)}")
    counts = {}
    for r in all_rows:
        t = (r["title"] or "").lower() or "professor"
        counts[t] = counts.get(t, 0) + 1
    print("\nTitle distribution:")
    for title, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"{n:3d}  {title}")

if __name__ == "__main__":
    main()
