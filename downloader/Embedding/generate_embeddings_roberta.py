import pandas as pd
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm

# -------- config --------
INPUT_FILE = "pdf_with_processed_text.csv"
MODEL_NAME = "roberta-base"
BATCH_SIZE = 8   
MAX_LEN = 256    
OUTPUT_EMB = "paper_embeddings_roberta.npy"
OUTPUT_META = "paper_embeddings_meta.csv"

# -------- load data --------
df = pd.read_csv(INPUT_FILE)
texts = df["processed_text"].astype(str).tolist()

# -------- load model --------
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# -------- embedding loop --------
all_embeddings = []

with torch.no_grad():
    for i in tqdm(range(0, len(texts), BATCH_SIZE)):
        batch_texts = texts[i:i + BATCH_SIZE]

        encoded = tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=MAX_LEN,
            return_tensors="pt"
        ).to(device)

        outputs = model(**encoded)
        last_hidden = outputs.last_hidden_state  # (B, T, 768)

        # mean pooling (mask padding)
        mask = encoded["attention_mask"].unsqueeze(-1)
        summed = torch.sum(last_hidden * mask, dim=1)
        counts = torch.clamp(mask.sum(dim=1), min=1e-9)
        mean_pooled = summed / counts

        all_embeddings.append(mean_pooled.cpu().numpy())

embeddings = np.vstack(all_embeddings)

# -------- save --------
np.save(OUTPUT_EMB, embeddings)
df.to_csv(OUTPUT_META, index=False)

print("Done!")
print("Embedding shape:", embeddings.shape)
