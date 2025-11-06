import requests
import json
import csv
from time import sleep

# --- Configuration Section ---

S2_API_KEY = "m5SlWgZXJL5kSt8GWBseX2yjtXDd6JA8a6unRcox" 
BASE_URL = "https://api.semanticscholar.org/graph/v1"

# ⚠️ NEW Input/Output File Paths
VALIDATED_ID_FILE = "validated_professors_ids.csv" 
SUCCESS_OUTPUT_FILE = "professors_papers_links_FINAL_with_institution.csv" # this the cvs after i corrct the id

HEADERS = {
    "x-api-key": S2_API_KEY,
    "Content-Type": "application/json"
}

# --- Core Functions (get_papers_links remains the same) ---

def get_papers_links(author_id: str, name: str) -> tuple[list, list]:
    """
    Fetches an author's papers and sorts them into most cited and most recent lists,
    with built-in retry logic for rate limiting (429 errors).
    """
    details_url = f"{BASE_URL}/author/{author_id}?fields=papers.title,papers.url,papers.citationCount,papers.year"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(details_url, headers=HEADERS, timeout=15)
            response.raise_for_status() 
            
            data = response.json()
            papers = data.get('papers', [])
            
            valid_papers = [p for p in papers if p.get('url')]
            
            most_cited = sorted(
                valid_papers, 
                key=lambda x: x.get('citationCount', 0), 
                reverse=True
            )[:10]
            
            most_recent = sorted(
                valid_papers, 
                key=lambda x: x.get('year') if x.get('year') is not None else 0, 
                reverse=True
            )[:10]

            return most_cited, most_recent 
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait_time = 2 ** attempt * 2 
                print(f"   🛑 Rate limit (429) hit for {name}. Waiting for {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                sleep(wait_time)
                continue 
            else:
                print(f"Error fetching papers for {name} (ID: {author_id}): {e}")
                return [], []

        except requests.exceptions.RequestException as e:
            print(f"Error fetching papers for {name} (ID: {author_id}): {e}")
            return [], []
            
    print(f"   ❌ Failed to fetch papers for {name} after {max_retries} retries due to persistent rate limiting.")
    return [], []

# --- Main Execution Logic (Modified to include Institution) ---

def main():
    """Reads the validated Author ID list and directly fetches papers for each ID."""
    
    # 1. Read Validated Professor IDs from CSV
    prof_data = []
    try:
        with open(VALIDATED_ID_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Ensure the necessary columns exist
            required_fields = ['Original_Name', 'Author_ID', 'Institution']
            if not all(field in reader.fieldnames for field in required_fields):
                 print(f"Error: Input file {VALIDATED_ID_FILE} must contain columns: {', '.join(required_fields)}.")
                 return
                 
            for row in reader:
                prof_data.append({
                    'name': row['Original_Name'].strip(),
                    'id': row['Author_ID'].strip(),
                    # 💡 NEW: Read the Institution field
                    'institution': row['Institution'].strip() 
                })
    except FileNotFoundError:
        print(f"Error: Input file {VALIDATED_ID_FILE} not found. Please create it.")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return


    successful_results = []
    
    print(f"Starting paper retrieval for {len(prof_data)} validated professors...")
    
    # 2. Iterate and Process IDs
    for prof in prof_data:
        name = prof['name']
        author_id = prof['id']
        institution = prof['institution'] # Store institution
        
        print(f"-> Processing professor: {name} ({institution}, ID: {author_id})...")
        
        # 3. Get Paper Links using the VALIDATED ID
        most_cited, most_recent = get_papers_links(author_id, name)
        
        successful_results.append({
            'Original Name': name,
            'Author ID': author_id,
            'Institution': institution, # Add to the result list
            'Most Cited Papers': most_cited,
            'Most Recent Papers': most_recent
        })
        print(f"   ✅ Successfully retrieved paper info for {name}.")
            
        sleep(1) 

    # 4. Output Results (Modified Fieldnames)

    print("\n--- Outputting Successful Matches Table ---")
    # 💡 NEW: Add Institution to fieldnames
    fieldnames = ['Institution', 'Professor Name (Original)', 'Author ID', 'Paper Type', 'Paper Title', 'Link']
    
    with open(SUCCESS_OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for p in successful_results:
            # Prepare common output fields
            common_fields = {
                'Institution': p['Institution'],
                'Professor Name (Original)': p['Original Name'],
                'Author ID': p['Author ID']
            }
            
            # Write Most Cited Papers
            for paper in p['Most Cited Papers']:
                writer.writerow(common_fields | {
                    'Paper Type': '10 Most Cited',
                    'Paper Title': paper.get('title', 'N/A'),
                    'Link': paper.get('url', 'N/A')
                })
            
            # Write Most Recent Papers
            for paper in p['Most Recent Papers']:
                writer.writerow(common_fields | {
                    'Paper Type': '10 Most Recent',
                    'Paper Title': paper.get('title', 'N/A'),
                    'Link': paper.get('url', 'N/A')
                })

    print(f"All paper links saved to {SUCCESS_OUTPUT_FILE}")

if __name__ == "__main__":
    main()