"""Evaluation helpers: threshold selection on validation data and metric reports."""
import numpy as np
from sklearn.metrics import (confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, average_precision_score)


def choose_threshold(y_val, p_val, beta=2.0):
    """Pick the probability threshold that maximises F-beta on the VALIDATION set.

    beta=2 weights recall twice as much as precision: for maintenance, a missed
    failure (false negative) is costlier than an unnecessary inspection.
    """
    best_t, best_score = 0.5, -1.0
    for t in np.arange(0.05, 0.96, 0.01):
        pred = (p_val >= t).astype(int)
        p = precision_score(y_val, pred, zero_division=0)
        r = recall_score(y_val, pred, zero_division=0)
        score = 0.0 if (p + r) == 0 else (1 + beta ** 2) * p * r / (beta ** 2 * p + r)
        if score > best_score:
            best_t, best_score = float(round(t, 2)), score
    return best_t


def report(y_true, p, threshold):
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, p)),
        "pr_auc": float(average_precision_score(y_true, p)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n_samples": int(len(y_true)),
        "n_failures": int(np.sum(y_true)),
    }
