import pandas as pd

# 1. Load data
df = pd.read_csv("pdf_with_abstracts_final.csv")


def build_processed_text(row):
    title = str(row["Paper Title"]).strip()
    abstract = str(row["Abstract"]).strip()

    # Determine whether an abstract is valid
    if pd.isna(row["Abstract"]) or len(abstract) < 20:
        # fallback：ONLY title
        return title
    else:
        # title + abstract
        return title + " " + abstract

# 2.check lens of text(title/title+abs)
# 3. Apply to dataframe
df["processed_text"] = df.apply(build_processed_text, axis=1)

df.to_csv("pdf_with_processed_text.csv", index=False)
print("Saved to pdf_with_processed_text.csv")
