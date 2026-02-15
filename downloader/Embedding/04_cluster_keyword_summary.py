import pandas as pd
from collections import Counter

df = pd.read_csv("papers_with_keywords_k10.csv")

summaries = []

for cid, group in df.groupby("cluster_id"):
    words = []
    for col in ["kw1", "kw2", "kw3"]:
        words += group[col].dropna().astype(str).tolist()

    counter = Counter(words)
    top_keywords = counter.most_common(20)

    summaries.append({
        "cluster_id": cid,
        "top_keywords": ", ".join([f"{w}({c})" for w, c in top_keywords])
    })

summary_df = pd.DataFrame(summaries).sort_values("cluster_id")
summary_df.to_csv("cluster_keyword_summary.csv", index=False)

print("Saved: cluster_keyword_summary.csv")
