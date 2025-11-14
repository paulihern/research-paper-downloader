import requests
import json
import csv
from time import sleep

# --- Configuration Section ---

# ⚠️ REPLACE with your actual Semantic Scholar API Key
# Note: Your API key is visible here for demonstration, but for security,
# it is highly recommended to store it as an environment variable in a real-world scenario.
S2_API_KEY = "m5SlWgZXJL5kSt8GWBseX2yjtXDd6JA8a6unRcox" 
BASE_URL = "https://api.semanticscholar.org/graph/v1"

# ⚠️ Input/Output File Paths
PROFESSOR_LIST_FILE = "professor_names.txt" 
# Output CSV file containing paper links (in table format)
SUCCESS_OUTPUT_FILE = "professors_papers_links.csv"
# Output file for names that need manual verification (mismatches or no ID found)
MANUAL_REVIEW_FILE = "manual_review_names.txt" 

# Configure API request headers
HEADERS = {
    "x-api-key": S2_API_KEY,
    "Content-Type": "application/json"
}

# --- Core Functions ---

def find_author_id(name: str) -> tuple[str | None, str | None]:
    """
    Searches for a Semantic Scholar Author ID based on the professor's name.
    
    The S2 API search is fuzzy and doesn't support institution filtering (UIUC/NU),
    so this function takes the first result as a potential match.
    
    Args:
        name: The full name of the professor.
    
    Returns:
        A tuple of (authorId, matchedName) or (None, None) if not found.
    """
    search_url = f"{BASE_URL}/author/search?query={name}"
    
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        response.raise_for_status() # Check for HTTP errors
        data = response.json()
        
        if data.get('data'):
            # Simplified logic: return the first matched author's ID and name
            first_match = data['data'][0]
            return first_match['authorId'], first_match['name']
        else:
            return None, None
            
    except requests.exceptions.RequestException as e:
        print(f"Error searching for {name}: {e}")
        return None, None

def get_papers_links(author_id: str) -> tuple[list, list]:
    """
    Fetches an author's papers and sorts them into most cited and most recent lists.
    
    The 'url' field is used as the link, as S2 API usually provides the paper's
    homepage (e.g., publisher or ArXiv) rather than a direct PDF link.
    
    Args:
        author_id: The Semantic Scholar Author ID.
    
    Returns:
        A tuple of (most_cited_papers_list, most_recent_papers_list).
    """
    # Request fields necessary for sorting and linking
    details_url = f"{BASE_URL}/author/{author_id}?fields=papers.title,papers.url,papers.citationCount,papers.year"
    
    try:
        response = requests.get(details_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        papers = data.get('papers', [])
        
        # Filter for papers that have a URL (potential link)
        valid_papers = [p for p in papers if p.get('url')]
        
        # 1. Most Cited Papers (Top 10)
        most_cited = sorted(
            valid_papers, 
            key=lambda x: x.get('citationCount', 0), 
            reverse=True
        )[:10]
        
        # 2. Most Recent Papers (Top 10)
        # ⚠️ FIX for TypeError: Safely handles 'year' being None by casting it to 0
        most_recent = sorted(
            valid_papers, 
            key=lambda x: x.get('year') if x.get('year') is not None else 0, 
            reverse=True
        )[:10]

        return most_cited, most_recent
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching papers for author ID {author_id}: {e}")
        return [], []

# --- Main Execution Logic ---

def main():
    """Reads the professor list, processes each name, and outputs the results."""
    
    # 1. Read Professor Names
    try:
        # Note: Changed from 'professors.txt' to 'professor_names.txt' to match the user's configuration
        with open(PROFESSOR_LIST_FILE, 'r', encoding='utf-8') as f:
            prof_names = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Input file {PROFESSOR_LIST_FILE} not found. Please create it and list one name per line.")
        return

    successful_matches = []
    manual_review_list = []
    
    print(f"Starting processing for {len(prof_names)} professors...")
    
    # 2. Iterate and Process Names
    for name in prof_names:
        print(f"-> Searching for professor: {name}...")
        
        author_id, matched_name = find_author_id(name)
        
        if author_id and matched_name:
            # Check for name mismatch to flag for manual review
            if name.lower().strip() != matched_name.lower().strip():
                 print(f"   ⚠️ Potential mismatch found: Matched name '{matched_name}' (ID: {author_id}), Original input: '{name}'. Needs manual confirmation.")
                 manual_review_list.append(f"Original Input: {name} | Matched Name: {matched_name} | Author ID: {author_id}")
            
            # 3. Get Paper Links
            most_cited, most_recent = get_papers_links(author_id)
            
            successful_matches.append({
                'Original Name': name,
                'Matched Name': matched_name,
                'Author ID': author_id,
                'Most Cited Papers': most_cited,
                'Most Recent Papers': most_recent
            })
            print(f"   ✅ Successfully retrieved paper info for {matched_name}.")
            
        else:
            print(f"   ❌ No matching Author ID found for: {name}")
            manual_review_list.append(f"Original Input: {name} | Status: No ID Found")
            
        # To respect API rate limits (e.g., 1 QPS for free tier)
        sleep(1) 

    # 4. Output Results

    # a) Output Manual Review List
    print("\n--- Outputting Manual Review List ---")
    with open(MANUAL_REVIEW_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(manual_review_list))
    print(f"Names requiring manual review saved to {MANUAL_REVIEW_FILE}")

    # b) Output Paper Links Table (CSV)
    print("\n--- Outputting Successful Matches Table ---")
    fieldnames = ['Professor Name (Original)', 'Author ID', 'Paper Type', 'Paper Title', 'Link']
    
    with open(SUCCESS_OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for p in successful_matches:
            # Write Most Cited Papers
            for paper in p['Most Cited Papers']:
                writer.writerow({
                    'Professor Name (Original)': p['Original Name'],
                    'Author ID': p['Author ID'],
                    'Paper Type': '10 Most Cited',
                    'Paper Title': paper.get('title', 'N/A'),
                    'Link': paper.get('url', 'N/A')
                })
            
            # Write Most Recent Papers
            for paper in p['Most Recent Papers']:
                writer.writerow({
                    'Professor Name (Original)': p['Original Name'],
                    'Author ID': p['Author ID'],
                    'Paper Type': '10 Most Recent',
                    'Paper Title': paper.get('title', 'N/A'),
                    'Link': paper.get('url', 'N/A')
                })

    print(f"Successful paper links table saved to {SUCCESS_OUTPUT_FILE}")

if __name__ == "__main__":
    main()