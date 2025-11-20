import requests
import csv
from time import sleep

# ========= Configuration =========

S2_API_KEY = "m5SlWgZXJL5kSt8GWBseX2yjtXDd6JA8a6unRcox"
BASE_URL = "https://api.semanticscholar.org/graph/v1"

VALIDATED_ID_FILE = "validated_ids.csv"          
SUCCESS_OUTPUT_FILE = "pdf_downloader.csv"       

HEADERS = {
    "x-api-key": S2_API_KEY,
    "Content-Type": "application/json"
}

# ========= Helper: Select BEST link =========

def choose_best_link(paper: dict) -> str:
    """
    Select best link:
    1) PDF
    2) DOI → publisher
    3) Semantic scholar page
    """
    # 1) PDF
    oa = paper.get("openAccessPdf")
    if isinstance(oa, dict):
        url = oa.get("url")
        if url:
            return url

    # 2) DOI
    ids = paper.get("externalIds", {})
    if isinstance(ids, dict):
        doi = ids.get("DOI") or ids.get("doi")
        if doi:
            return f"https://doi.org/{doi}"

    # 3) fallback
    return paper.get("url", "N/A")


# ========= Core: Fetch papers =========

def get_papers_links(author_id: str, name: str):
    """
    Fetch paper info + extra fields (PDF / DOI / citation / year).
    """
    query = (
        f"{BASE_URL}/author/{author_id}"
        "?fields=papers.title,"
        "papers.url,"
        "papers.citationCount,"
        "papers.year,"
        "papers.openAccessPdf,"
        "papers.externalIds"
    )

    for attempt in range(3):
        try:
            resp = requests.get(query, headers=HEADERS, timeout=15)
            resp.raise_for_status()

            data = resp.json()
            papers = data.get("papers", [])

            # Only keep papers with semantic link
            valid = [p for p in papers if p.get("url")]

            # ---- Sort them ----
            most_cited = sorted(
                valid,
                key=lambda x: x.get("citationCount", 0),
                reverse=True
            )[:10]

            most_recent = sorted(
                valid,
                key=lambda x: x.get("year") or 0,
                reverse=True
            )[:10]

            return most_cited, most_recent

        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:
                wait = 2 ** attempt * 2
                print(f"   429 too many requests → sleeping {wait}s ...")
                sleep(wait)
                continue
            else:
                print(f"HTTP error for {name}: {e}")
                return [], []

        except Exception as e:
            print(f"Request error for {name}: {e}")
            return [], []

    print(f"   ❌ Failed for {name} after retries")
    return [], []


# ========= Main Pipeline =========

def main():

    # 1. Load validated IDs
    profs = []
    try:
        with open(VALIDATED_ID_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            required = ["Original_Name", "Author_ID", "Institution"]
            if not all(col in reader.fieldnames for col in required):
                print("❌ validated_ids.csv missing required columns.")
                print("Required:", required)
                return

            for row in reader:
                profs.append({
                    "name": row["Original_Name"].strip(),
                    "id": row["Author_ID"].strip(),
                    "institution": row["Institution"].strip()
                })

    except FileNotFoundError:
        print(f"❌ File not found: {VALIDATED_ID_FILE}")
        return

    print(f"👉 Fetching papers for {len(profs)} professors...\n")

    output_rows = []

    # 2. Fetch papers
    for p in profs:
        name = p["name"]
        author_id = p["id"]
        inst = p["institution"]

        print(f"===== {name} ({inst}) | ID = {author_id} =====")

        most_cited, most_recent = get_papers_links(author_id, name)

        # Append to output
        for paper in most_cited:
            output_rows.append({
                "Institution": inst,
                "Professor Name (Original)": name,
                "Author ID": author_id,
                "Paper Type": "Most Cited",
                "Paper Title": paper.get("title", "N/A"),
                "Year": paper.get("year", ""),
                "Citation Count": paper.get("citationCount", 0),
                "Semantic Scholar URL": paper.get("url", "N/A"),
                "pdf_Link": choose_best_link(paper)
            })

        for paper in most_recent:
            output_rows.append({
                "Institution": inst,
                "Professor Name (Original)": name,
                "Author ID": author_id,
                "Paper Type": "Most Recent",
                "Paper Title": paper.get("title", "N/A"),
                "Year": paper.get("year", ""),
                "Citation Count": paper.get("citationCount", 0),
                "Semantic Scholar URL": paper.get("url", "N/A"),
                "Final Link": choose_best_link(paper)
            })

        sleep(1)

    # 3. Save CSV
    fieldnames = [
        "Institution",
        "Professor Name (Original)",
        "Author ID",
        "Paper Type",
        "Paper Title",
        "Year",
        "Citation Count",
        "Semantic Scholar URL",
        "Final Link"
    ]

    with open(SUCCESS_OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\n🎉 Done! Results saved to {SUCCESS_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
