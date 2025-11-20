import csv

REVIEWED_FILE = "reviewed.txt"
NONEED_FILE = "noneed_review.txt"
OUTPUT_FILE = "validated_ids.csv"


def parse_reviewed(path: str):
    """
    Parse reviewed.txt into a list of dicts:
    { "Original_Name": ..., "Author_ID": ..., "Institution": ... }

    - Uses section headers '# UIUC' / '# NU' to set Institution.
    - Supports both 'Author ID:' and 'Status:' formats.
    - If there are multiple IDs in one line (e.g. Mickey), split into multiple rows.
    """
    records = []
    current_institution = ""

    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line.startswith("Original Input:"):
                continue

            # Split "Original Input: NAME | ..." part
            try:
                left, right = line.split("|", 1)
            except ValueError:
                # No "|" – malformed line, skip
                continue

            name = left.replace("Original Input:", "").strip()

            # Section headers like "# UIUC" / "# NU"
            if name.startswith("#"):
                label = name.lstrip("#").strip().upper()
                if "UIUC" in label:
                    current_institution = "UIUC"
                elif "NU" in label:
                    current_institution = "NU"
                else:
                    current_institution = ""
                # Don't create a row for section headers
                continue

            # Extract ID from "Author ID:" or "Status:"
            id_str = None
            if "Author ID:" in right:
                id_str = right.split("Author ID:", 1)[1].strip()
            elif "Status:" in right:
                id_str = right.split("Status:", 1)[1].strip()
            else:
                # No ID info found
                continue

            # Clean up cases like "Status: 2041393"
            id_str = id_str.replace("Status:", "").strip()

            # Handle multiple IDs in one line (e.g., Mickey with a Chinese comma)
            id_str_normalized = id_str.replace("，", ",")
            id_parts = [part.strip() for part in id_str_normalized.split(",") if part.strip()]

            for author_id in id_parts:
                records.append({
                    "Original_Name": name,
                    "Author_ID": author_id,
                    "Institution": current_institution
                })

    return records


def parse_noneed(path: str):
    """
    Parse noneed_review.txt into a list of dicts:
    { "Original_Name": ..., "Author_ID": ..., "Institution": "" }

    There is no institution info in this file, so Institution is left empty.
    """
    records = []

    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line.startswith("Original Input:"):
                continue

            try:
                left, right = line.split("|", 1)
            except ValueError:
                continue

            name = left.replace("Original Input:", "").strip()

            if "Author ID:" not in right:
                continue

            author_id = right.split("Author ID:", 1)[1].strip()

            records.append({
                "Original_Name": name,
                "Author_ID": author_id,
                "Institution": ""  # unknown here; can be filled later
            })

    return records


def main():
    # 1. Parse both files
    reviewed_records = parse_reviewed(REVIEWED_FILE)
    noneed_records = parse_noneed(NONEED_FILE)

    # Names that already appear in reviewed.txt
    reviewed_names = {r["Original_Name"] for r in reviewed_records}

    # 2. Start merged list with all reviewed records (they are the most trusted)
    merged = list(reviewed_records)

    # 3. Add from noneed_review those names that do NOT appear in reviewed
    for rec in noneed_records:
        if rec["Original_Name"] not in reviewed_names:
            merged.append(rec)

    # 4. Write the final CSV
    fieldnames = ["Original_Name", "Author_ID", "Institution"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    print(f"✅ Wrote {len(merged)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
