import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

embeddings = np.load("paper_embeddings_roberta.npy")

from sklearn.manifold import TSNE

tsne = TSNE(
    n_components=2,
    perplexity=30,
    learning_rate=200,
    random_state=42
)

tsne_2d = tsne.fit_transform(embeddings)
print(tsne_2d.shape)

k = 10
kmeans = KMeans(
    n_clusters=k,
    random_state=42,
    n_init=10
)

cluster_labels = kmeans.fit_predict(embeddings)
np.save("cluster_labels_k10.npy", cluster_labels)

print("Clustering done.")
print("Cluster counts:", np.bincount(cluster_labels))


INPUT_CSV = "paper_embeddings_meta.csv"
OUTPUT_CSV = "papers_clustered_k10.csv"


df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")

assert len(df) == len(cluster_labels), f"Row mismatch: df={len(df)} vs labels={len(cluster_labels)}"

df["cluster_id"] = cluster_labels
df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

print(f"Saved CSV with cluster_id: {OUTPUT_CSV}")


import matplotlib.pyplot as plt

plt.figure(figsize=(6, 5))
sc = plt.scatter(
    tsne_2d[:, 0],
    tsne_2d[:, 1],
    c=cluster_labels,
    cmap="tab10",
    s=10,
    alpha=0.7
)

plt.title("t-SNE of Paper Embeddings (Colored by KMeans Cluster)")
plt.tight_layout()
plt.colorbar(sc, label="Cluster ID")
plt.savefig("tsne_colored_by_cluster.png", dpi=200)
plt.show()


import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

pca = PCA(n_components=2, random_state=42)
pca_2d = pca.fit_transform(embeddings)

print("PCA explained variance ratio:", pca.explained_variance_ratio_)

# --- Plot PCA colored by cluster ---
plt.figure(figsize=(6, 5))
sc = plt.scatter(
    pca_2d[:, 0],
    pca_2d[:, 1],
    c=cluster_labels,
    cmap="tab10",
    s=10,
    alpha=0.7
)
plt.xlabel("PC1")
plt.ylabel("PC2")
plt.title("PCA of Paper Embeddings (Colored by KMeans Cluster)")
plt.tight_layout()
plt.colorbar(sc, label="Cluster ID")
plt.savefig("pca_colored_by_cluster.png", dpi=200)
plt.show()

