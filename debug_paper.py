# debug.py
import json
import requests
from modules import config

S2_BASE = config.S2_BASE
TITLE = "The structure and migration of twin boundaries in tetragonal β-Sn: An application of machine learning based interatomic potentials"

def search_paper_by_title(title):
    """Search for a paper by title and return the full API response."""
    url = f"{S2_BASE}/paper/search"
    params = {
        "query": title,
        "limit": 1,
        "fields": ",".join([
            "paperId",
            "title",
            "authors",
            "year",
            "citationCount",
            "openAccessPdf",
            "isOpenAccess",
            "url",
            "venue",
            "externalIds",
            "publicationTypes"
        ]),
    }
    print(f"Searching Semantic Scholar for:\n  {title}\n")
    r = requests.get(url, params=params, timeout=45)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    data = search_paper_by_title(TITLE)
    print("\n--- RAW RESPONSE ---\n")
    print(json.dumps(data, indent=2, ensure_ascii=False))
