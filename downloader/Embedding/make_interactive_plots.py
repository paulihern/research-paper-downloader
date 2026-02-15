import os
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import plotly.express as px

# ====== paths (your paths) ======
CSV_IN = "pdf_with_abstracts_final_k10.csv"
EMB_NPY = "paper_embeddings_roberta.npy"
LAB_NPY = "cluster_labels_k10.npy"

OUT_TSNE_HTML = "tsne_interactive_k10.html"
OUT_PCA_HTML  = "pca_interactive_k10.html"

# ====== load ======
df = pd.read_csv(CSV_IN, encoding="utf-8-sig", engine="python", on_bad_lines="skip")
emb = np.load(EMB_NPY)
labels = np.load(LAB_NPY).astype(int)
print("CSV rows:", len(df))
print("Embeddings shape:", emb.shape)
print("Labels shape:", labels.shape)

# truncate to align (just in case)
n = min(len(df), emb.shape[0], labels.shape[0])
if len(df) != n or emb.shape[0] != n or labels.shape[0] != n:
    print("⚠️ Row count mismatch. Truncating to n =", n)
    df = df.iloc[:n].copy()
    emb = emb[:n]
    labels = labels[:n]

# ====== find columns robustly ======
def pick_col(candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

title_col = pick_col(["Paper Title", "title", "Title"])
abs_col   = pick_col(["Abstract", "abstract"])
prof_col  = pick_col(["Professor", "professor", "Faculty", "faculty", "Professor Name"])
id_col    = pick_col(["DOI", "doi", "paper_id", "Paper ID", "URL", "url"])

if title_col is None:
    raise ValueError(f"Cannot find a title column. Columns are: {list(df.columns)[:30]} ...")

# cluster column: prefer CSV's if exists, else use npy
cluster_col = None
for c in df.columns:
    if c.lower() in ["cluster_id", "cluster", "kmeans_cluster", "clusterid"]:
        cluster_col = c
        break

if cluster_col is None:
    df["cluster_id"] = labels
    cluster_col = "cluster_id"
else:
    # optional: overwrite with npy to ensure consistency
    # df[cluster_col] = labels
    pass

# build hover text fields
df["_title"] = df[title_col].astype(str).fillna("")
df["_prof"] = df[prof_col].astype(str).fillna("") if prof_col else ""
df["_id"] = df[id_col].astype(str).fillna("") if id_col else ""
df["_abs_preview"] = df[abs_col].astype(str).fillna("").str.slice(0, 200) if abs_col else ""

# ====== PCA 2D ======
pca = PCA(n_components=2, random_state=42)
pca_2d = pca.fit_transform(emb)
pca_df = pd.DataFrame({
    "x": pca_2d[:, 0],
    "y": pca_2d[:, 1],
    "cluster": df[cluster_col].astype(int),
    "title": df["_title"],
    "professor": df["_prof"],
    "id": df["_id"],
    "abstract_preview": df["_abs_preview"],
})
COLOR_SEQ = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # olive
    "#17becf",  # cyan
]
COLOR_MAP = {str(i): COLOR_SEQ[i] for i in range(10)}
CAT_ORDER = [str(i) for i in range(10)]

fig_pca = px.scatter(
    pca_df, x="x", y="y", color="cluster",
    color_discrete_map=COLOR_MAP,
    hover_data={"id": True, "professor": True, "title": True, "abstract_preview": True, "x": False, "y": False},
    title="PCA (2D) of Paper Embeddings — hover to see paper info"
)
fig_pca.write_html(OUT_PCA_HTML)
print("✅ Saved PCA interactive:", OUT_PCA_HTML)

# ====== t-SNE 2D ======
# t-SNE might take a bit but does NOT recompute embeddings
tsne = TSNE(n_components=2, perplexity=30, learning_rate=200, random_state=42)
tsne_2d = tsne.fit_transform(emb)

tsne_df = pd.DataFrame({
    "x": tsne_2d[:, 0],
    "y": tsne_2d[:, 1],
    "cluster": df[cluster_col].astype(int),
    "title": df["_title"],
    "professor": df["_prof"],
    "id": df["_id"],
    "abstract_preview": df["_abs_preview"],
})
fig_tsne = px.scatter(
    tsne_df, x="x", y="y", color="cluster",
    color_discrete_map=COLOR_MAP,
    hover_data={"id": True, "professor": True, "title": True, "abstract_preview": True, "x": False, "y": False},
    title="t-SNE (2D) of Paper Embeddings — hover to see paper info"
)
fig_tsne.write_html(OUT_TSNE_HTML)
print("✅ Saved t-SNE interactive:", OUT_TSNE_HTML)

print("\nDone. Open the HTML files in your browser.")