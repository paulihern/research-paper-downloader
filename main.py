from modules.scrapers import FacultyScraper
from modules.indexer import ScholarIndexer

def main():
    # --- STEP 1: Scrape professors ---
    print("\n--- Updating professor list ---")
    scraper = FacultyScraper()
    # scraper.update_uiuc_directory()
    # scraper.update_uiuc_professor_papers()
    scraper.update_northwestern_directory()
    scraper.update_northwestern_professor_papers()


    # --- STEP 2: Fetch papers ---
    print("\n--- Updating paper metadata ---")
    # indexer = ScholarIndexer()
    # indexer.update_from_professors_file()



    # --- STEP 3: Download PDFs (future step) ---
    ### DOWNLOADER not yet implemented as there is a problem finding the right Author Ids from the names, as there are too many ppl with same name
    # print("\n--- Downloading missing PDFs ---")
    # downloader = PaperDownloader()
    # downloader.download_missing()

if __name__ == "__main__":
    main()


