import pandas as pd
import requests
import time

def fetch_from_s2(paper_id):
    """Try Semantic Scholar first."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields=abstract"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('abstract')
    except: return None
    return None

def fetch_from_openalex(doi):
    """Fallback 1: Try OpenAlex if S2 fails."""
    if not doi: return None
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            index = resp.json().get('abstract_inverted_index')
            if index:
                # Reconstruct text from inverted index
                word_map = {pos: w for w, positions in index.items() for pos in positions}
                return " ".join(word_map[i] for i in sorted(word_map.keys()))
    except: return None
    return None

def main():
    df = pd.read_csv('pdf_downloader.csv')
    results = []

    print("--- Starting Multi-source Enrichment ---")
    for i, row in df.iterrows():
        # 1. Try S2 via ID
        ss_url = str(row.get('Semantic Scholar URL', ''))
        paper_id = ss_url.split('/')[-1] if 'semanticscholar.org' in ss_url else None
        abstract = fetch_from_s2(paper_id) if paper_id else None
        
        # 2. If S2 failed, Try OpenAlex via DOI (from Final Link)
        if not abstract:
            import re
            doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', str(row.get('Final Link')), re.IGNORECASE)
            if doi_match:
                abstract = fetch_from_openalex(doi_match.group(0))
        
        # 3. Final Fallback: Mark as missing
        if abstract:
            results.append(abstract)
            print(f"[{i+1}] Retrieved successfully.")
        else:
            results.append("ABSTRACT_MISSING_FALLBACK_TO_TITLE")
            print(f"[{i+1}] All sources failed. Marked for fallback.")
            
        time.sleep(0.5)

    df['Abstract'] = results
    df.to_csv('pdf_with_abstracts.csv', index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    main()