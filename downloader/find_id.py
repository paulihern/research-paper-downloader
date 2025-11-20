import requests
import csv
from time import sleep

# --- Configuration Section ---

S2_API_KEY = "m5SlWgZXJL5kSt8GWBseX2yjtXDd6JA8a6unRcox"
BASE_URL = "https://api.semanticscholar.org/graph/v1"

# Input: list of professor names (one per line)
PROFESSOR_LIST_FILE = "professor_names.txt"

# Output: names that require manual review (mismatched or no ID found)
MANUAL_REVIEW_FILE = "need_review.txt"

# Output: names that look safely matched (name matches well)
AUTO_OK_FILE = "noneed_review.txt"

HEADERS = {
    "x-api-key": S2_API_KEY,
    "Content-Type": "application/json"
}

# --- Core Functions ---

def find_author_id(name: str) -> tuple[str | None, str | None]:
    """
    Search for a Semantic Scholar Author ID based on the professor's name.

    This version:
    - requests multiple candidates
    - chooses the one with the largest paperCount.
    """
    search_url = (
        f"{BASE_URL}/author/search"
        f"?query={name}"
        f"&fields=name,authorId,paperCount"
        f"&limit=20"
    )

    try:
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        candidates = data.get("data", [])
        if not candidates:
            return None, None

        # Choose the candidate with the largest paperCount
        best = max(
            candidates,
            key=lambda a: a.get("paperCount") if a.get("paperCount") is not None else -1
        )

        author_id = best.get("authorId")
        matched_name = best.get("name")

        if not author_id:
            return None, None

        return author_id, matched_name

    except requests.exceptions.RequestException as e:
        print(f"Error searching for {name}: {e}")
        return None, None

# --- Main Execution Logic ---

def main():
    """
    Reads the professor list, processes each name, and outputs two lists:
      - need_review.txt: names that require manual review
      - noneed_review.txt: names that look safely matched
    """

    # 1. Read professor names
    try:
        with open(PROFESSOR_LIST_FILE, "r", encoding="utf-8") as f:
            prof_names = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Input file {PROFESSOR_LIST_FILE} not found. Please create it and list one name per line.")
        return

    need_review_lines = []
    auto_ok_lines = []

    print(f"Starting processing for {len(prof_names)} professors...")

    # 2. Iterate over all names
    for name in prof_names:
        print(f"-> Searching for professor: {name}...")

        author_id, matched_name = find_author_id(name)

        if author_id and matched_name:
            # Normalize for comparison: ignore spaces and case
            norm_input = name.lower().replace(" ", "")
            norm_match = matched_name.lower().replace(" ", "")

            if norm_input == norm_match:
                # Names match well -> accept automatically
                line = f"Original Input: {name} | Matched Name: {matched_name} | Author ID: {author_id}"
                auto_ok_lines.append(line)
                print(f"   ✅ Auto match accepted: {matched_name} (ID: {author_id})")
            else:
                # Potential mismatch -> send to manual review
                print(
                    f"   ⚠️ Potential mismatch: matched '{matched_name}' (ID: {author_id}), "
                    f"original '{name}'. Sending to manual review."
                )
                line = f"Original Input: {name} | Matched Name: {matched_name} | Author ID: {author_id}"
                need_review_lines.append(line)
        else:
            # No candidate found at all
            print(f"   ❌ No matching Author ID found for: {name}")
            need_review_lines.append(f"Original Input: {name} | Status: No ID Found")

        # Respect API rate limits (e.g., 1 QPS)
        sleep(1)

    # 3. Write outputs

    # a) Names requiring manual review
    print("\n--- Writing manual review list (need_review.txt) ---")
    with open(MANUAL_REVIEW_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(need_review_lines))
    print(f"Names requiring manual review saved to {MANUAL_REVIEW_FILE}")

    # b) Names that look safely matched
    print("\n--- Writing auto-accepted list (noneed_review.txt) ---")
    with open(AUTO_OK_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(auto_ok_lines))
    print(f"Auto-accepted matches saved to {AUTO_OK_FILE}")

    print("\nDone. ✅")

if __name__ == "__main__":
    main()
