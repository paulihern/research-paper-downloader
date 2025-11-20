"""
End-to-end workflow runner for the RA project.

Steps:
0. Run scrape_professors.py to scrape raw faculty names
   - Output: name_screped.txt
   - Manually clean name_screped.txt and save as professor_names.txt

1. Run find_id.py to generate need_review.txt and noneed_review.txt
   (uses professor_names.txt as input)

2. Manually review need_review.txt and save the cleaned result as reviewed.txt

3. Run build_validated_csv.py to create validated_ids.csv
   (merges reviewed.txt + noneed_review.txt)

4. Run fetch_papers.py to fetch 10 most cited + 10 most recent papers
   and save them into pdf_downloader.csv
"""

from pathlib import Path
import sys

# ---- import main() functions from existing scripts ----
from scrape_professors import main as scrape_professors_main   # STEP 0
from find_id import main as find_id_main                       # STEP 1
from build_validated_csv import main as build_validated_csv_main  # STEP 3
# STEP 4 (fetch_papers) will be imported inside the step function


# ------------ STEP 0: scrape professors ------------

def step_0_scrape_professors():
    """
    Step 0:
    - Run scrape_professors.py to scrape faculty names from UIUC + NU websites.
    - That script writes:
        * professors.csv
        * name_screped.txt  (raw name list)
    - After this step, manually open name_screped.txt,
      clean / adjust names, and save the final list as professor_names.txt.
    """
    print("\n===== STEP 0: Scraping faculty names (scrape_professors.py) =====")
    scrape_professors_main()
    print("✅ Step 0 finished:")
    print("   - professors.csv")
    print("   - name_screped.txt  (raw names)")
    print("👉 Please open 'name_screped.txt', clean it, and save as 'professor_names.txt' before running step_1_find_ids().\n")


# ------------ STEP 1: find IDs ------------

def step_1_find_ids():
    """
    Step 1:
    - Uses professor_names.txt as input (you created it by cleaning name_screped.txt).
    - find_id.py will:
        * search Semantic Scholar for each professor
        * write:
            - noneed_review.txt  (matches you trust directly)
            - need_review.txt    (matches that need manual checking / missing IDs)
    """
    print("\n===== STEP 1: Finding author IDs (find_id.py) =====")
    find_id_main()
    print("✅ Step 1 finished: need_review.txt and noneed_review.txt should now be updated.\n")


# ------------ STEP 2: manual review of IDs ------------

def step_2_wait_for_manual_review():
    """
    Step 2:
    - You manually review need_review.txt and create reviewed.txt.
    """
    print("===== STEP 2: Manual review required =====")
    print("Please:")
    print("  1) Open need_review.txt")
    print("  2) Manually confirm / fix IDs")
    print("  3) Save the final result as reviewed.txt in the SAME folder")
    print()
    input("When you are done and reviewed.txt is ready, press Enter to continue...")


# ------------ STEP 3: build validated_ids.csv ------------

def step_3_build_validated_csv():
    """
    Step 3:
    - build_validated_csv.py will merge:
        * reviewed.txt
        * noneed_review.txt
      into:
        * validated_ids.csv  (Original_Name, Author_ID, Institution)
    """
    print("\n===== STEP 3: Building validated_ids.csv =====")
    reviewed_path = Path("reviewed.txt")
    noneed_path = Path("noneed_review.txt")

    if not reviewed_path.exists():
        print("❌ Error: reviewed.txt not found. Did you finish the manual review?")
        sys.exit(1)

    if not noneed_path.exists():
        print("❌ Error: noneed_review.txt not found. Did you run Step 1 (find_id.py)?")
        sys.exit(1)

    build_validated_csv_main()
    print("✅ Step 3 finished: validated_ids.csv created.\n")


# ------------ STEP 4: fetch papers ------------

def step_4_fetch_papers():
    """
    Step 4:
    - fetch_papers.py reads validated_ids.csv
      and writes pdf_downloader.csv with 10 most cited + 10 most recent papers.
    """
    print("\n===== STEP 4: Fetching papers from Semantic Scholar (fetch_papers.py) =====")
    csv_path = Path("validated_ids.csv")
    if not csv_path.exists():
        print("❌ Error: validated_ids.csv not found.")
        print("   Did Step 3 (build_validated_csv.py) run successfully?")
        sys.exit(1)

    from fetch_papers import main as fetch_papers_main  # import here so steps 0–3 still work even if this file is WIP

    fetch_papers_main()
    print("✅ Step 4 finished: pdf_downloader.csv created.\n")


if __name__ == "__main__":
    print("========================================")
    print("   RA Pipeline: Step-by-step Runner")
    print("   Uncomment the steps you want to run.")
    print("========================================\n")

    # 🔽🔽🔽 CONTROL PANEL 🔽🔽🔽
    # Delete the leading '#' for the steps you want to execute.

    # step_0_scrape_professors()
    # step_1_find_ids()
    # step_2_wait_for_manual_review()
    # step_3_build_validated_csv()
    # step_4_fetch_papers()
