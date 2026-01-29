import pandas as pd
import requests
import time

# ======================================================
# CREDENTIALS & CONFIGURATION
# ======================================================
API_KEY = "m5SlWgZXJL5kSt8GWBseX2yjtXDd6JA8a6unRcox"
INPUT_FILE = "pdf_with_abstracts.csv"
OUTPUT_FILE = "pdf_with_abstracts_final.csv"
S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/"

# Official header required by Semantic Scholar
HEADERS = {"x-api-key": API_KEY}

def fetch_abstract_safe(paper_id):
    """
    Fetches abstract using the API Key with error handling.
    """
    url = f"{S2_API_URL}{paper_id}?fields=abstract"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 200:
            return response.json().get('abstract')
        elif response.status_code == 403:
            return "AUTH_ERROR_CHECK_KEY"
        elif response.status_code == 429:
            print("   [Rate Limit] Too fast! Sleeping for 5 seconds...")
            time.sleep(5)
            return fetch_abstract_safe(paper_id)
        else:
            return None
    except Exception as e:
        print(f"   [Error] {e}")
        return None

def main():
    # 1. Load your existing data
    df = pd.read_csv(INPUT_FILE)
    
    # 2. Identify missing rows
    mask = (df['Abstract'] == "ABSTRACT_MISSING_FALLBACK_TO_TITLE") | (df['Abstract'].isna())
    missing_indices = df[mask].index
    total_to_patch = len(missing_indices)
    
    print(f"--- Starting Authorized Patching: {total_to_patch} entries ---")

    # 3. Execution Loop
    for idx, row_idx in enumerate(missing_indices):
        s2_url = str(df.at[row_idx, 'Semantic Scholar URL'])
        paper_id = s2_url.split('/')[-1] if 'semanticscholar.org' in s2_url else None
        
        if paper_id:
            print(f"[{idx+1}/{total_to_patch}] Requesting ID: {paper_id}")
            abstract = fetch_abstract_safe(paper_id)
            
            if abstract and len(str(abstract)) > 30:
                df.at[row_idx, 'Abstract'] = abstract
                print("    Success: Abstract retrieved.")
            elif abstract == "AUTH_ERROR_CHECK_KEY":
                print("    Critical: API Key rejected (403). Stopping script.")
                break
            else:
                print("    Notice: Abstract not found in S2 Database.")
        
        # 4. RATE LIMIT COMPLIANCE (CRITICAL)
        # Your limit is 1 req/sec. We wait 1.2s to be safe.
        time.sleep(1.2)

    # 5. Save the final results
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"\n--- Process Complete! Final saved to: {OUTPUT_FILE} ---")

if __name__ == "__main__":
    main()