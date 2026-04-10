"""
RA Task: Student–Professor Research Matching Pipeline
Author: Zhuoran
=======================================================
Steps:
  1. Build embeddings for students and professors (via sentence-transformers)
  2. Construct interaction matrix X_ij using cosine similarity
  3. Use Gemini to generate candidate research attributes
  4. Embed attributes; compute student–attribute and professor–attribute similarities
  5. Build attribute-based representations for students and professors
  6. Approximate X using attribute representations
  7. Compare linear model (dot product) vs nonlinear model (sklearn regression)

Requirements:
    pip install sentence-transformers scikit-learn pandas numpy tqdm google-generativeai
"""

import ast
import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import normalize
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PROFESSOR_CSV = "professors_profiles.csv"       # ← adjust paths if needed
STUDENT_CSV   = "students_virtual_engineering_profiles_v2_less_ai.csv"

EMBED_MODEL   = "all-MiniLM-L6-v2"             # fast, 384-dim; swap for larger if needed
N_STUDENTS    = None                            # subsample for speed; set None for all 4000
N_ATTRIBUTES  = 30                             # number of LLM-generated research attributes
GEMINI_MODEL  = "gemini-2.5-flash"             # or "gemini-1.5-pro" for higher quality
GEMINI_API_KEY = "AIzaSyDJcEcPQWrlA23Nx9hfPlyXM7vfvj4DUcw"    # ← paste your key here, or set env var GEMINI_API_KEY

OUTPUT_DIR    = Path("ra_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# 0. LOAD DATA
# ─────────────────────────────────────────────

def load_data():
    profs    = pd.read_csv(PROFESSOR_CSV)
    students = pd.read_csv(STUDENT_CSV)
    if N_STUDENTS:
        students = students.sample(n=N_STUDENTS, random_state=42).reset_index(drop=True)
    print(f"Loaded {len(profs)} professors, {len(students)} students")
    return profs, students


def make_professor_text(row):
    """Combine professor fields into a single descriptive string."""
    parts = [row.get("prof_text", "")]
    kw = row.get("top_keywords", "")
    try:
        kw_list = ast.literal_eval(kw) if isinstance(kw, str) else kw
        parts.append("Keywords: " + ", ".join(kw_list[:10]))
    except Exception:
        parts.append(str(kw))
    return " ".join(str(p) for p in parts if p)


def make_student_text(row):
    """Combine student fields into a single descriptive string."""
    parts = [
        row.get("interest_profile", ""),
        "Research interests: " + str(row.get("research_interests", "")),
        "Methods/tools: " + str(row.get("methods_tools", "")),
        "Keywords: " + str(row.get("profile_keywords", "")),
    ]
    return " ".join(str(p) for p in parts if p)


# ─────────────────────────────────────────────
# 1. EMBEDDINGS
# ─────────────────────────────────────────────

def get_embeddings(texts: list[str], model_name: str = EMBED_MODEL) -> np.ndarray:
    """
    Returns L2-normalized embeddings of shape (N, D).
    Uses sentence-transformers locally.
    """
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    print(f"  Encoding {len(texts)} texts with {model_name}…")
    embs = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    return np.array(embs, dtype=np.float32)


def cosine_sim_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """
    A: (m, d),  B: (n, d) — both L2-normalized.
    Returns (m, n) cosine similarity matrix.
    """
    return A @ B.T


# ─────────────────────────────────────────────
# 2. INTERACTION MATRIX
# ─────────────────────────────────────────────

def build_interaction_matrix(student_embs: np.ndarray,
                              prof_embs: np.ndarray) -> np.ndarray:
    """
    X[i, j] = cosine_sim(student_i, professor_j)
    Shape: (n_students, n_professors)
    """
    X = cosine_sim_matrix(student_embs, prof_embs)
    print(f"Interaction matrix shape: {X.shape}, "
          f"mean={X.mean():.3f}, std={X.std():.3f}")
    return X


# ─────────────────────────────────────────────
# 3. LLM-GENERATED RESEARCH ATTRIBUTES
# ─────────────────────────────────────────────

def get_attributes(profs: pd.DataFrame) -> list[str]:
    """
    Call Gemini to generate research attribute phrases from professor data.
    Raises on any failure — no fallback.
    """
    import os
    import google.generativeai as genai

    api_key = GEMINI_API_KEY if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE" \
          else os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("No Gemini API key found. Set GEMINI_API_KEY in config or env var GEMINI_API_KEY.")
    genai.configure(api_key=api_key)

    all_keywords = []
    for kw in profs["top_keywords"].dropna():
        try:
            all_keywords.extend(ast.literal_eval(kw))
        except Exception:
            all_keywords.append(str(kw))
    kw_sample = ", ".join(list(dict.fromkeys(all_keywords))[:60])

    all_areas = []
    for fa in profs["top_factories"].dropna():
        try:
            all_areas.extend(ast.literal_eval(fa))
        except Exception:
            all_areas.append(str(fa))
    area_sample = ", ".join(list(dict.fromkeys(all_areas))[:20])

    prompt = f"""You are a research domain expert helping to build a student\u2013professor matching system.

Below is a summary of research keywords and areas from {len(profs)} engineering professors:

Research areas: {area_sample}

Sample keywords: {kw_sample}

Task: Generate exactly {N_ATTRIBUTES} short, distinct research attribute phrases (5\u201310 words each) that best span the research landscape above. Each attribute should be specific enough to differentiate research directions, yet broad enough that both students and professors can be meaningfully scored against it.

Return ONLY a JSON array of {N_ATTRIBUTES} strings, no other text. Example format:
[\"attribute one here\", \"attribute two here\", ...]"""

    print(f"Calling Gemini API ({GEMINI_MODEL}) to generate research attributes\u2026")
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    raw = re.sub(r"```json|```", "", response.text.strip()).strip()

    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        raise ValueError(f"Could not parse Gemini response as JSON array. Raw output:\n{raw}")

    attributes = json.loads(match.group())
    print(f"  Generated {len(attributes)} attributes via Gemini API")
    return attributes[:N_ATTRIBUTES]


# ─────────────────────────────────────────────
# 4 & 5. ATTRIBUTE-BASED REPRESENTATIONS
# ─────────────────────────────────────────────

def build_attribute_representations(student_embs, prof_embs, attr_embs):
    S_attr = cosine_sim_matrix(student_embs, attr_embs)
    P_attr = cosine_sim_matrix(prof_embs, attr_embs)
    # normalize so dot product ≈ cosine sim
    S_attr = S_attr / (np.linalg.norm(S_attr, axis=1, keepdims=True) + 1e-8)
    P_attr = P_attr / (np.linalg.norm(P_attr, axis=1, keepdims=True) + 1e-8)
    print(f"Attribute representation shapes — students: {S_attr.shape}, professors: {P_attr.shape}")
    return S_attr, P_attr


# ─────────────────────────────────────────────
# 6 & 7. APPROXIMATE X & MODEL COMPARISON
# ─────────────────────────────────────────────

def approximate_X_linear(S_attr: np.ndarray, P_attr: np.ndarray) -> np.ndarray:
    """
    Linear approximation: X̂[i,j] = dot(S_attr[i], P_attr[j])
    = (S_attr @ P_attr.T)
    This is a bilinear / inner-product model.
    """
    X_hat = S_attr @ P_attr.T
    return X_hat


def build_pairwise_features(S_attr: np.ndarray,
                             P_attr: np.ndarray,
                             X_true: np.ndarray,
                             max_pairs: int = 40_000):
    """
    Build a flat feature matrix for regression:
      row = [s_attr_vec | p_attr_vec | element-wise product | abs diff]
      label = X_true[i,j]

    max_pairs caps the dataset size for tractability.
    """
    n_s, n_p = X_true.shape
    idx_s, idx_p = np.meshgrid(np.arange(n_s), np.arange(n_p), indexing='ij')
    idx_s = idx_s.ravel()
    idx_p = idx_p.ravel()

    if len(idx_s) > max_pairs:
        rng = np.random.default_rng(0)
        sel = rng.choice(len(idx_s), max_pairs, replace=False)
        idx_s, idx_p = idx_s[sel], idx_p[sel]

    s_feat = S_attr[idx_s]          # (N, n_attr)
    p_feat = P_attr[idx_p]          # (N, n_attr)
    prod   = s_feat * p_feat        # element-wise product
    diff   = np.abs(s_feat - p_feat)

    features = np.hstack([s_feat, p_feat, prod, diff])   # (N, 4*n_attr)
    labels   = X_true[idx_s, idx_p]

    return features, labels


def evaluate_model(name, model, X_tr, y_tr, X_te, y_te):
    model.fit(X_tr, y_tr)
    y_pred = model.predict(X_te)
    mse = mean_squared_error(y_te, y_pred)
    r2  = r2_score(y_te, y_pred)
    print(f"  {name:35s}  MSE={mse:.5f}  R²={r2:.4f}")
    return {"model": name, "mse": mse, "r2": r2}


def run_model_comparison(S_attr, P_attr, X_true):
    print("\n── Model Comparison ──────────────────────────────────────────")

    # --- Linear approximation (no sklearn needed) ---
    X_hat_linear = approximate_X_linear(S_attr, P_attr)
    linear_mse = mean_squared_error(X_true.ravel(), X_hat_linear.ravel())
    linear_r2  = r2_score(X_true.ravel(), X_hat_linear.ravel())
    print(f"  {'Linear (dot product, attribute space)':35s}  "
          f"MSE={linear_mse:.5f}  R²={linear_r2:.4f}")

    # --- Build pairwise feature dataset for sklearn models ---
    print("\nBuilding pairwise feature dataset for nonlinear models…")
    features, labels = build_pairwise_features(S_attr, P_attr, X_true)
    X_tr, X_te, y_tr, y_te = train_test_split(
        features, labels, test_size=0.2, random_state=42
    )
    print(f"  Train: {X_tr.shape[0]}, Test: {X_te.shape[0]}, Features: {X_tr.shape[1]}")

    results = []

    # Ridge (regularized linear)
    results.append(evaluate_model(
        "Ridge Regression (sklearn)",
        Ridge(alpha=1.0), X_tr, y_tr, X_te, y_te
    ))

    # Random Forest
    results.append(evaluate_model(
        "Random Forest Regressor",
        RandomForestRegressor(n_estimators=100, n_jobs=-1, random_state=42),
        X_tr, y_tr, X_te, y_te
    ))

    # Gradient Boosting
    results.append(evaluate_model(
        "Gradient Boosting Regressor",
        GradientBoostingRegressor(n_estimators=200, learning_rate=0.05,
                                   max_depth=4, random_state=42),
        X_tr, y_tr, X_te, y_te
    ))

    results.append({"model": "Linear (dot product, attr space)",
                    "mse": linear_mse, "r2": linear_r2})
    return pd.DataFrame(results).sort_values("r2", ascending=False)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Student–Professor Matching Pipeline")
    print("=" * 60)

    # 0. Load
    profs, students = load_data()

    prof_texts    = profs.apply(make_professor_text, axis=1).tolist()
    student_texts = students.apply(make_student_text, axis=1).tolist()

    # 1. Embeddings
    print("\n── Step 1: Computing embeddings ──────────────────────────────")
    prof_embs    = get_embeddings(prof_texts)
    student_embs = get_embeddings(student_texts)

    np.save(OUTPUT_DIR / "prof_embs.npy",    prof_embs)
    np.save(OUTPUT_DIR / "student_embs.npy", student_embs)

    # 2. Interaction matrix
    print("\n── Step 2: Building interaction matrix ───────────────────────")
    X_true = build_interaction_matrix(student_embs, prof_embs)
    np.save(OUTPUT_DIR / "X_interaction.npy", X_true)

    # 3. Generate attributes via LLM
    print("\n── Step 3: Generating research attributes via Gemini ─────────")
    attributes = get_attributes(profs)
    print("  Sample attributes:", attributes[:5])
    (OUTPUT_DIR / "attributes.json").write_text(json.dumps(attributes, indent=2))

    # 4. Embed attributes
    print("\n── Step 4: Embedding attributes ──────────────────────────────")
    attr_embs = get_embeddings(attributes)
    np.save(OUTPUT_DIR / "attr_embs.npy", attr_embs)

    # 5. Attribute-based representations
    print("\n── Step 5: Building attribute-based representations ──────────")
    S_attr, P_attr = build_attribute_representations(student_embs, prof_embs, attr_embs)
    np.save(OUTPUT_DIR / "S_attr.npy", S_attr)
    np.save(OUTPUT_DIR / "P_attr.npy", P_attr)

    # 6 & 7. Model comparison
    results_df = run_model_comparison(S_attr, P_attr, X_true)

    print("\n── Summary ───────────────────────────────────────────────────")
    print(results_df.to_string(index=False))
    results_df.to_csv(OUTPUT_DIR / "model_comparison.csv", index=False)

    print(f"\nAll outputs saved to: {OUTPUT_DIR.resolve()}/")
    print("Done ✓")


if __name__ == "__main__":
    main()