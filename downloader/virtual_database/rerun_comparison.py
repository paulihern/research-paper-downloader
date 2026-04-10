import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from pathlib import Path

OUTPUT_DIR = Path("ra_outputs")

S_attr = np.load(OUTPUT_DIR / "S_attr.npy")
P_attr = np.load(OUTPUT_DIR / "P_attr.npy")
X_true = np.load(OUTPUT_DIR / "X_interaction.npy")

print(f"S_attr: {S_attr.shape}, P_attr: {P_attr.shape}, X_true: {X_true.shape}")


def build_pairwise_features(S_attr, P_attr, X_true, max_pairs=40_000):
    n_s, n_p = X_true.shape
    idx_s, idx_p = np.meshgrid(np.arange(n_s), np.arange(n_p), indexing='ij')
    idx_s = idx_s.ravel()
    idx_p = idx_p.ravel()
    if len(idx_s) > max_pairs:
        rng = np.random.default_rng(0)
        sel = rng.choice(len(idx_s), max_pairs, replace=False)
        idx_s, idx_p = idx_s[sel], idx_p[sel]
    s_feat = S_attr[idx_s]
    p_feat = P_attr[idx_p]
    features = np.hstack([s_feat, p_feat, s_feat * p_feat, np.abs(s_feat - p_feat)])
    labels = X_true[idx_s, idx_p]
    return features, labels


def evaluate_model(name, model, X_tr, y_tr, X_te, y_te):
    model.fit(X_tr, y_tr)
    y_pred = model.predict(X_te)
    mse = mean_squared_error(y_te, y_pred)
    r2 = r2_score(y_te, y_pred)
    print(f"  {name:35s}  MSE={mse:.5f}  R²={r2:.4f}")
    return {"model": name, "mse": mse, "r2": r2}


def run_model_comparison(S_attr, P_attr, X_true):
    print("\n── Model Comparison ──────────────────────────────────────────")

    features, labels = build_pairwise_features(S_attr, P_attr, X_true)
    X_tr, X_te, y_tr, y_te = train_test_split(
        features, labels, test_size=0.2, random_state=42
    )
    print(f"  Train: {X_tr.shape[0]}, Test: {X_te.shape[0]}, Features: {X_tr.shape[1]}")

    s_te = X_te[:, :30]
    p_te = X_te[:, 30:60]
    linear_pred = (s_te * p_te).sum(axis=1)
    linear_mse = mean_squared_error(y_te, linear_pred)
    linear_r2 = r2_score(y_te, linear_pred)
    print(f"  {'Linear (dot product, attribute space)':35s}  "
          f"MSE={linear_mse:.5f}  R²={linear_r2:.4f}")

    results = []
    results.append(evaluate_model(
        "Ridge Regression (sklearn)",
        Ridge(alpha=1.0), X_tr, y_tr, X_te, y_te
    ))
    results.append(evaluate_model(
        "Random Forest Regressor",
        RandomForestRegressor(n_estimators=100, n_jobs=-1, random_state=42),
        X_tr, y_tr, X_te, y_te
    ))
    results.append(evaluate_model(
        "Gradient Boosting Regressor",
        GradientBoostingRegressor(n_estimators=200, learning_rate=0.05,
                                   max_depth=4, random_state=42),
        X_tr, y_tr, X_te, y_te
    ))
    results.append({"model": "Linear (dot product, attr space)",
                    "mse": linear_mse, "r2": linear_r2})
    return pd.DataFrame(results).sort_values("r2", ascending=False)


results_df = run_model_comparison(S_attr, P_attr, X_true)
print("\n── Summary ───────────────────────────────────────────────────")
print(results_df.to_string(index=False))
results_df.to_csv(OUTPUT_DIR / "model_comparison.csv", index=False)