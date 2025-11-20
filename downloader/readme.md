# Downloader Workflow

This folder contains a pipeline that:
1. Scrapes Mechanical Engineering faculty from UIUC & Northwestern.
2. Finds Semantic Scholar author IDs for each professor.
3. Allows manual review of ambiguous matches.
4. Fetches the 10 most cited and 10 most recent papers per professor.
5. Outputs a table with PDF / publisher links.

## Step-by-step

1. Run `scrape_professors.py`  
   → outputs `name_screped.txt`, then manually clean it to `professor_names.txt`.

2. Run `find_id.py`  
   → outputs `need_review.txt` and `noneed_review.txt`.

3. Manually review `need_review.txt` and save as `reviewed.txt`.

4. Run `build_validated_csv.py`  
   → outputs `validated_ids.csv`.

5. Run `fetch_papers.py`  
   → outputs `pdf_downloader.csv`.

Or simply run:

```bash
python main.py
