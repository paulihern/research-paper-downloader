import pandas as pd
import re
import time
import requests

# Professional Academic API: OpenAlex (No API key required for low volume)
OPENALEX_API_URL = "https://api.openalex.org/works/"

def extract_doi_from_link(url):
    """
    Extracts DOI (Digital Object Identifier) from a given URL using Regex.
    Standard DOI format: 10.xxxx/xxxx
    """
    if pd.isna(url):
        return None
    # Regular expression to catch DOI pattern in various URL structures
    doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', str(url), re.IGNORECASE)
    return doi_match.group(0) if doi_match else None

def get_abstract_from_openalex(doi):
    """
    Fetches the abstract from OpenAlex API using the DOI.
    OpenAlex uses an 'Inverted Index' for abstracts to save space.
    """
    try:
        # Querying OpenAlex via DOI
        response = requests.get(f"{OPENALEX_API_URL}https://doi.org/{doi}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            # OpenAlex returns abstracts in an 'inverted_index' format
            inverted_index = data.get('abstract_inverted_index')
            if inverted_index:
                # Reconstructing the abstract from the inverted index
                # The index maps words to their positions in the text
                word_positions = {}
                for word, positions in inverted_index.items():
                    for pos in positions:
                        word_positions[pos] = word
                
                # Sort positions and join words to form the full string
                reconstructed_abstract = " ".join([word_positions[i] for i in sorted(word_positions.keys())])
                return reconstructed_abstract
    except Exception as e:
        return None
    return None

def main():
    input_csv = 'pdf_downloader.csv'
    output_csv = 'pdf_with_abstracts.csv'
    
    print(f"--- Loading data from {input_csv} ---")
    df = pd.read_csv(input_csv)
    
    # Initialize the new column
    df['Abstract'] = "Abstract Not Available"
    
    print(f"--- Starting Metadata Enrichment (Total Papers: {len(df)}) ---")
    
    for index, row in df.iterrows():
        # Step 1: Extract DOI from the 'Final Link' column
        final_link = row.get('Final Link', '')
        doi = extract_doi_from_link(final_link)
        
        if doi:
            # Step 2: Fetch abstract using the extracted DOI
            abstract = get_abstract_from_openalex(doi)
            if abstract:
                df.at[index, 'Abstract'] = abstract
                print(f"[{index+1}] Success: Abstract retrieved via DOI: {doi}")
            else:
                print(f"[{index+1}] Failed: Abstract not found in OpenAlex for DOI: {doi}")
        else:
            print(f"[{index+1}] Skipped: No valid DOI found in Final Link.")
            
        # Polite API delay to prevent rate-limiting
        time.sleep(0.2)

    # Step 3: Save the enriched dataset
    # Using utf-8-sig to ensure Excel compatibility for special characters
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n--- Process Completed. Enriched file saved as: {output_csv} ---")

if __name__ == "__main__":
    main()
