import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer

# -------- FILES --------
STUDENTS_FILE = "students_virtual_engineering_profiles_v2_less_ai.csv"
PROFS_FILE = "professors_profiles.csv"
OUTPUT_FILE = "matches_top5_engineering.csv"

TOP_K = 5

# -------- LOAD --------
students = pd.read_csv(STUDENTS_FILE)
profs = pd.read_csv(PROFS_FILE)

# -------- BUILD STUDENT TEXT --------
def safe_list(x):
    if pd.isna(x):
        return []
    s = str(x).strip()
    return [t.strip(" '\"") for t in s.strip("[]()").split(",") if t.strip()]

def build_student_text(row):
    parts = [
        str(row.get("interest_profile", "")),
        "Research interests: " + "; ".join(safe_list(row.get("research_interests"))),
        "Keywords: " + "; ".join(safe_list(row.get("profile_keywords"))),
        "Methods/tools: " + "; ".join(safe_list(row.get("methods_tools")))
    ]
    return " ".join(parts)

students["student_text"] = students.apply(build_student_text, axis=1)
profs["prof_text"] = profs["prof_text"].astype(str)

# -------- EMBEDDING --------
model = SentenceTransformer("all-MiniLM-L6-v2")

student_embeddings = model.encode(
    students["student_text"].tolist(),
    normalize_embeddings=True,
    show_progress_bar=True
)

prof_embeddings = model.encode(
    profs["prof_text"].tolist(),
    normalize_embeddings=True,
    show_progress_bar=True
)

# -------- COSINE SIMILARITY --------
similarity_matrix = np.matmul(student_embeddings, prof_embeddings.T)

# -------- TOP K MATCHES --------
rows = []

for i in range(len(students)):
    scores = similarity_matrix[i]
    top_indices = np.argsort(scores)[-TOP_K:][::-1]

    for rank, j in enumerate(top_indices):
        rows.append({
            "student_id": students.loc[i, "student_id"],
            "student_major": students.loc[i, "major"],
            "student_school": students.loc[i, "school"],
            "professor_name": profs.loc[j, "professor_name"],
            "prof_institution": profs.loc[j, "institution"],
            "fitness_score": float(scores[j]),
            "rank": rank + 1
        })

matches = pd.DataFrame(rows)
matches.to_csv(OUTPUT_FILE, index=False)

print("Matching complete.")
print("Saved to:", OUTPUT_FILE)
