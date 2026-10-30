"""Train the predictive-maintenance model and export versioned artifacts.

Usage:  python ml/train.py
Outputs (ml/artifacts/):  model_<version>.json, metrics.json, feature_importance.json,
confusion_matrix.png, feature_importance.png.  The model is also copied to
backend/src/shared/model/model.json so the Lambda package can load it.
"""
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preprocessing as pp  # noqa: E402
from evaluate import choose_threshold, report  # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

ART_DIR = os.path.join(pp.ROOT, "ml", "artifacts")
LAMBDA_MODEL = os.path.join(pp.ROOT, "backend", "src", "shared", "model", "model.json")


def export_forest(rf):
    """Flatten each sklearn tree into plain lists (p_fail per node) for pure-Python inference."""
    trees = []
    for est in rf.estimators_:
        t = est.tree_
        v = t.value[:, 0, :]
        p_fail = (v[:, 1] / v.sum(axis=1)).round(6)
        trees.append({
            "left": t.children_left.tolist(),
            "right": t.children_right.tolist(),
            "feature": t.feature.tolist(),
            "threshold": [float(x) for x in t.threshold],
            "p_fail": p_fail.tolist(),
        })
    return trees


def plot_artifacts(cm, importances, names):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4.2, 3.8))
    mat = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
    ax.imshow(mat, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, mat[i, j], ha="center", va="center", fontsize=14,
                    color="white" if mat[i, j] > mat.max() / 2 else "black")
    ax.set_xticks([0, 1], ["Pred healthy", "Pred failure"])
    ax.set_yticks([0, 1], ["Actual healthy", "Actual failure"])
    ax.set_title("Confusion matrix (test set)")
    fig.tight_layout()
    fig.savefig(os.path.join(ART_DIR, "confusion_matrix.png"), dpi=150)
    plt.close(fig)

    order = np.argsort(importances)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh([names[i] for i in order], importances[order], color="#2b6cb0")
    ax.set_title("Random Forest feature importance")
    fig.tight_layout()
    fig.savefig(os.path.join(ART_DIR, "feature_importance.png"), dpi=150)
    plt.close(fig)


def main():
    os.makedirs(ART_DIR, exist_ok=True)
    df = pp.clean(pp.load_raw())
    X, y = pp.to_xy(df)
    X_tr, X_val, X_te, y_tr, y_val, y_te = pp.split(X, y)
    print(f"rows={len(df)} failures={int(y.sum())} ({y.mean():.2%}) "
          f"train/val/test={len(y_tr)}/{len(y_val)}/{len(y_te)}")

    # Class imbalance: handled with class weights inside training only (no resampling of val/test).
    rf = RandomForestClassifier(n_estimators=100, max_depth=12, min_samples_leaf=3,
                                class_weight="balanced_subsample", random_state=pp.SEED, n_jobs=-1)
    candidates = {
        "random_forest": rf,
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=pp.SEED)),
        "gradient_boosting": GradientBoostingClassifier(random_state=pp.SEED),
    }

    comparison = {}
    for name, model in candidates.items():
        model.fit(X_tr, y_tr)
        p_val = model.predict_proba(X_val)[:, 1]
        thr = choose_threshold(y_val, p_val)
        comparison[name] = {"validation": report(y_val, p_val, thr),
                            "test": report(y_te, model.predict_proba(X_te)[:, 1], thr)}
        t = comparison[name]["test"]
        print(f"{name:20s} thr={thr:.2f} P={t['precision']:.3f} R={t['recall']:.3f} "
              f"F1={t['f1']:.3f} AUC={t['roc_auc']:.3f}")

    # Deployed model = Random Forest (the project baseline).
    thr = comparison["random_forest"]["validation"]["threshold"]
    test_rep = comparison["random_forest"]["test"]
    trees = export_forest(rf)
    body = {
        "decision_threshold": thr,
        "medium_threshold": round(thr / 2, 2),
        "feature_names": pp.FEATURE_NAMES,
        "trees": trees,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:8]
    version = f"rf-{datetime.now(timezone.utc):%Y%m%d}-{digest}"
    model_json = {"model_version": version, **body}

    versioned = os.path.join(ART_DIR, f"model_{version}.json")
    with open(versioned, "w", encoding="utf-8") as fh:
        json.dump(model_json, fh, separators=(",", ":"))
    os.makedirs(os.path.dirname(LAMBDA_MODEL), exist_ok=True)
    shutil.copyfile(versioned, LAMBDA_MODEL)

    imp = rf.feature_importances_
    importance = {n: round(float(v), 4) for n, v in sorted(zip(pp.FEATURE_NAMES, imp), key=lambda kv: -kv[1])}
    metrics = {
        "model_version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": pp.SEED,
        "dataset": {"rows": int(len(df)), "failures": int(y.sum()), "failure_rate": float(y.mean()),
                    "split": {"train": int(len(y_tr)), "validation": int(len(y_val)), "test": int(len(y_te))}},
        "decision_threshold": thr,
        "medium_threshold": body["medium_threshold"],
        "threshold_rule": "maximise F2 on the validation split; medium risk starts at half the decision threshold",
        "deployed_model": "random_forest",
        "test": test_rep,
        "comparison": comparison,
        "excluded_columns": pp.LEAKY_COLUMNS + ["UDI", "Product ID"],
    }
    with open(os.path.join(ART_DIR, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    with open(os.path.join(ART_DIR, "feature_importance.json"), "w", encoding="utf-8") as fh:
        json.dump(importance, fh, indent=2)
    plot_artifacts(test_rep["confusion_matrix"], imp, pp.FEATURE_NAMES)

    # Sanity: exported pure-Python forest must agree with sklearn.
    sys.path.insert(0, os.path.join(pp.ROOT, "backend", "src"))
    from shared.model import failure_probability
    diffs = [abs(failure_probability(model_json, X_te[i].tolist()) - rf.predict_proba(X_te[i:i + 1])[0, 1])
             for i in range(0, len(X_te), 20)]
    print(f"export parity max diff = {max(diffs):.2e}")
    print(f"saved {versioned}")


if __name__ == "__main__":
    main()
