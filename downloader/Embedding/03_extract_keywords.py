import os
import pandas as pd
from keybert import KeyBERT

BASE = os.path.dirname(__file__)
INPUT = os.path.join(BASE, "papers_clustered_k10.csv")
OUTPUT = os.path.join(BASE, "papers_with_keywords_k10.csv")

TEXT_COL = "processed_text"

df = pd.read_csv(INPUT)

if TEXT_COL not in df.columns:
    raise ValueError(f"{TEXT_COL} not found in columns.")

kw_model = KeyBERT(model="all-MiniLM-L6-v2")

kw1, kw2, kw3 = [], [], []

for txt in df[TEXT_COL].fillna("").astype(str):
    txt = txt.strip()
    if not txt:
        kw1.append("")
        kw2.append("")
        kw3.append("")
        continue

    kws = kw_model.extract_keywords(
        txt,
        keyphrase_ngram_range=(1, 2),
        stop_words="english",
        top_n=3,
        use_mmr=True,
        diversity=0.5,
    )

    keys = [k for k, _ in kws] + ["", "", ""]
    kw1.append(keys[0])
    kw2.append(keys[1])
    kw3.append(keys[2])

df["kw1"] = kw1
df["kw2"] = kw2
df["kw3"] = kw3

df.to_csv(OUTPUT, index=False)
print("Saved:", OUTPUT)
