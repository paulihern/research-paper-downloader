import matplotlib.pyplot as plt
import numpy as np
embeddings = np.load("paper_embeddings_roberta.npy")


from sklearn.manifold import TSNE

tsne = TSNE(
    n_components=2,
    perplexity=30,
    learning_rate=200,
    random_state=42
)

tsne_2d = tsne.fit_transform(embeddings)

plt.figure(figsize=(6, 5))
plt.scatter(tsne_2d[:, 0], tsne_2d[:, 1], s=10, alpha=0.6)
plt.title("t-SNE of Paper Embeddings")
plt.tight_layout()
plt.savefig("tsne_2d.png")
plt.show()
