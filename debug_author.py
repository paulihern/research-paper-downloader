# debug_author.py
import json
import requests
from modules import config

S2_BASE = config.S2_BASE

def search_author_by_name(name: str, limit: int = 5):
    """Search Semantic Scholar for authors by name and print basic info."""
    url = f"{S2_BASE}/author/search"
    params = {
        "query": name,
        "limit": limit,
        "fields": "authorId,name,affiliations,url,paperCount,citationCount"
    }

    print(f"\n🔍 Searching Semantic Scholar for author:\n  {name}")
    print(f"URL: {url}")
    print(f"Params: {params}\n")

    try:
        r = requests.get(url, params=params, timeout=45)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return []

    try:
        data = r.json()
    except Exception as e:
        print(f"❌ Error parsing JSON: {e}")
        print("Raw text:", r.text[:500])
        return []

    hits = data.get("data", [])
    if not hits:
        print("⚠️ No author matches found.")
        return []

    print("--- Author Candidates ---")
    for i, h in enumerate(hits):
        print(f"{i+1}. {h.get('name')} ({h.get('authorId')})")
        print(f"   Affiliations: {h.get('affiliations')}")
        print(f"   Papers: {h.get('paperCount')}, Citations: {h.get('citationCount')}")
        print(f"   URL: {h.get('url')}\n")

    return hits

def fetch_full_author_info(author_id: str):
    """Fetch full author info and print it."""
    url = f"{S2_BASE}/author/{author_id}"
    params = {
        "fields": "authorId,name,homepage,url,externalIds,paperCount,citationCount,hIndex"
    }

    print(f"\n🔍 Fetching full author info for authorId: {author_id}")
    try:
        r = requests.get(url, params=params, timeout=45)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Error parsing JSON: {e}")
        return None

    print("\n--- FULL AUTHOR METADATA ---\n")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data

def fetch_first_paper(author_id: str):
    """Fetch only the first paper for the given author and print all metadata."""
    url = f"{S2_BASE}/author/{author_id}/papers"
    params = {
        "limit": 1,
        "fields": ",".join([
            "paperId",
            "corpusId",
            "externalIds",
            "title",
            "abstract",
            "venue",
            "publicationVenue",
            "year",
            "referenceCount",
            "citationCount",
            "influentialCitationCount",
            "isOpenAccess",
            "openAccessPdf",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
            "publicationTypes",
            "publicationDate",
            "journal",
            "citationStyles",
            "authors",
            "url"
        ])
    }

    print(f"\n🔍 Fetching first paper for authorId: {author_id}")
    try:
        r = requests.get(url, params=params, timeout=45)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Error parsing JSON: {e}")
        return None

    papers = data.get("data", [])
    if papers:
        first_paper = papers[0]
        print("\n--- FIRST PAPER METADATA ---\n")
        print(json.dumps(first_paper, indent=2, ensure_ascii=False))
        return first_paper
    else:
        print("⚠️ No papers found for this author.")
        return None

if __name__ == "__main__":
    NAME = "Nikhil Chandra  Admal"
    candidates = search_author_by_name(NAME)

    for c in candidates:
        author_id = c.get("authorId")
        if author_id:
            fetch_full_author_info(author_id)
            fetch_first_paper(author_id)  # <-- Added step
