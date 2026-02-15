import pandas as pd
from collections import Counter

INPUT = "../Embedding/papers_refined_factory.csv"

OUTPUT = "professors_profiles.csv"

# ---- helpers ----
def clean_str(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    return s if s else None

def top_k_from_series(series, k):
    vals = [clean_str(v) for v in series]
    vals = [v for v in vals if v]
    return [w for w, _ in Counter(vals).most_common(k)]

def uniq_keep_order(vals, k=None):
    seen = set()
    out = []
    for v in vals:
        v = clean_str(v)
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
        if k and len(out) >= k:
            break
    return out

# ---- main ----
def main():
    df = pd.read_csv(INPUT)

    need = ["Professor Name (Original)", "Institution", "Paper Title", "Citation Count",
            "refined_factory", "kw1", "kw2", "kw3"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    prof_rows = []

    for prof, g in df.groupby("Professor Name (Original)", dropna=True):
        institution = g["Institution"].iloc[0]
        n_papers = len(g)

        # top factories (by frequency)
        top_factories = top_k_from_series(g["refined_factory"], k=5)

        # top keywords from kw1/kw2/kw3 (by frequency)
        kw_series = pd.concat([g["kw1"], g["kw2"], g["kw3"]], ignore_index=True)
        top_keywords = top_k_from_series(kw_series, k=10)

        # top cited paper titles (unique)
        g_sorted = g.sort_values("Citation Count", ascending=False)
        top_titles = uniq_keep_order(g_sorted["Paper Title"].tolist(), k=3)

        # Build prof_text (concise, embedding-friendly)
        parts = []
        if top_factories:
            parts.append(f"Research areas: {', '.join(top_factories[:3])}.")
        if top_keywords:
            parts.append(f"Key topics: {', '.join(top_keywords[:6])}.")
        if top_titles:
            parts.append(f"Representative papers: {top_titles[0]}.")
        prof_text = " ".join(parts)

        prof_rows.append({
            "professor_name": prof,
            "institution": institution,
            "n_papers": n_papers,
            "top_factories": top_factories,
            "top_keywords": top_keywords,
            "top_papers": top_titles,
            "prof_text": prof_text
        })

    out = pd.DataFrame(prof_rows).sort_values(["institution", "professor_name"]).reset_index(drop=True)
    out.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"Wrote {OUTPUT} ({len(out)} professors)")

if __name__ == "__main__":
    main()
