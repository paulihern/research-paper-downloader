import numpy as np
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

embeddings = np.load("paper_embeddings_roberta.npy")

pca = PCA(n_components=2)
pca_2d = pca.fit_transform(embeddings)

print("Explained variance ratio:", pca.explained_variance_ratio_)

plt.figure(figsize=(6, 5))
plt.scatter(pca_2d[:, 0], pca_2d[:, 1], s=10, alpha=0.6)
plt.xlabel("PC1")
plt.ylabel("PC2")
plt.title("PCA of Paper Embeddings")
plt.tight_layout()
plt.savefig("pca_2d.png")
plt.show()
