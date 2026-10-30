import json
import os

import numpy as np
import pytest

import preprocessing as pp
from evaluate import choose_threshold, report
from shared import features, model as mdl

ROOT = pp.ROOT
pytestmark = pytest.mark.skipif(not os.path.exists(pp.CSV_PATH), reason="dataset not downloaded")


def test_dataset_schema_and_size():
    df = pp.load_raw()
    assert len(df) == 10000
    for col in pp.REQUIRED_COLUMNS:
        assert col in df.columns


def test_leakage_columns_not_in_features():
    for leaky in pp.LEAKY_COLUMNS + ["UDI", "Product ID", "Machine failure"]:
        assert leaky not in features.FEATURE_NAMES


def test_clean_removes_missing_and_bad_types():
    df = pp.load_raw().head(20).copy()
    df.loc[0, pp.COL_TORQUE] = np.nan
    df.loc[1, pp.COL_TYPE] = "X"
    assert len(pp.clean(df)) == 18


def test_split_is_reproducible_and_stratified():
    X, y = pp.to_xy(pp.clean(pp.load_raw()))
    a = pp.split(X, y)
    b = pp.split(X, y)
    assert all(np.array_equal(i, j) for i, j in zip(a, b))
    rates = [a[3].mean(), a[4].mean(), a[5].mean()]
    assert max(rates) - min(rates) < 0.005
    assert len(a[0]) + len(a[1]) + len(a[2]) == len(y)


def test_feature_vector_shape_and_one_hot():
    v = features.build_features(298.1, 308.6, 1500, 40, 100, "H")
    assert len(v) == len(features.FEATURE_NAMES)
    assert v[-3:] == [0.0, 0.0, 1.0]


def test_exported_model_matches_saved_metrics():
    m = mdl.load_model()
    with open(os.path.join(ROOT, "ml", "artifacts", "metrics.json")) as fh:
        metrics = json.load(fh)
    assert m["model_version"] == metrics["model_version"]
    assert m["decision_threshold"] == metrics["decision_threshold"]
    assert metrics["test"]["recall"] > 0.6 and metrics["test"]["roc_auc"] > 0.9


def test_inference_reproduces_reported_test_metrics():
    """Pure-Python inference on the held-out test split reproduces the saved confusion matrix."""
    m = mdl.load_model()
    X, y = pp.to_xy(pp.clean(pp.load_raw()))
    _, _, X_te, _, _, y_te = pp.split(X, y)
    p = np.array([mdl.failure_probability(m, row.tolist()) for row in X_te])
    rep = report(y_te, p, m["decision_threshold"])
    with open(os.path.join(ROOT, "ml", "artifacts", "metrics.json")) as fh:
        saved = json.load(fh)["test"]
    assert rep["confusion_matrix"] == saved["confusion_matrix"]


@pytest.mark.parametrize("p,expected", [(0.0, "LOW"), (0.239, "LOW"), (0.24, "MEDIUM"), (0.479, "MEDIUM"), (0.48, "HIGH"), (1.0, "HIGH")])
def test_risk_classification_boundaries(p, expected):
    m = {"decision_threshold": 0.48, "medium_threshold": 0.24}
    assert mdl.risk_level(m, p) == expected


def test_risk_and_class_always_consistent():
    m = mdl.load_model()
    for torque in (20, 40, 60, 70):
        for wear in (0, 150, 240):
            r = mdl.predict(m, dict(air_temperature=298.5, process_temperature=307.5, rotational_speed=1300,
                                    torque=torque, tool_wear=wear, machine_type="M"))
            assert (r["risk_level"] == "HIGH") == (r["predicted_class"] == "FAILURE_PREDICTED")


def test_threshold_selection_prefers_recall():
    y = np.array([0] * 90 + [1] * 10)
    p = np.concatenate([np.linspace(0, 0.4, 90), np.linspace(0.3, 0.9, 10)])
    t = choose_threshold(y, p)
    assert 0.05 <= t <= 0.95
    assert report(y, p, t)["recall"] >= 0.8
