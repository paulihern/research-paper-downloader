import pandas as pd
from keybert import KeyBERT

INPUT_CSV = "pdf_with_abstracts_final_k10.csv"
OUTPUT_CSV = "paper_keywords_k10.csv"

TITLE_COL = "title"
ABSTRACT_COL = "abstract"     
ID_COL = None                  

def build_text(row):
    title = str(row.get(TITLE_COL, "") or "").strip()
    ab = str(row.get(ABSTRACT_COL, "") or "").strip()
    if ab and ab.lower() != "nan":
        return f"{title}. {ab}"
    return title

def main():
    df = pd.read_csv(INPUT_CSV)

    df["text_input"] = df.apply(build_text, axis=1)

    kw_model = KeyBERT(model="all-MiniLM-L6-v2")  

    kw1_list, kw2_list, kw3_list = [], [], []
    for txt in df["text_input"].fillna(""):
        txt = str(txt).strip()
        if not txt:
            kw1_list.append("")
            kw2_list.append("")
            kw3_list.append("")
            continue

        kws = kw_model.extract_keywords(
            txt,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            top_n=3,
            use_mmr=True,
            diversity=0.5,
        )
        # kws: list of tuples [(keyword, score), ...]
        keys = [k for k, _ in kws] + ["", "", ""]
        kw1_list.append(keys[0])
        kw2_list.append(keys[1])
        kw3_list.append(keys[2])

    df["kw1"] = kw1_list
    df["kw2"] = kw2_list
    df["kw3"] = kw3_list

    keep_cols = []
    if ID_COL and ID_COL in df.columns:
        keep_cols.append(ID_COL)

    for c in ["professor", "cluster_id", TITLE_COL, ABSTRACT_COL, "kw1", "kw2", "kw3"]:
        if c in df.columns:
            keep_cols.append(c)

    out = df[keep_cols] if keep_cols else df
    out.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved: {OUTPUT_CSV}  rows={len(out)}")

if __name__ == "__main__":
    main()
