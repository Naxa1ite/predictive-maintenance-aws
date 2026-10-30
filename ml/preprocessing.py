"""Dataset loading and preprocessing for the AI4I 2020 dataset.

Leakage control: the failure-mode columns (TWF, HDF, PWF, OSF, RNF) are
components of the target ("Machine failure" is 1 iff any of them is 1), so
they are dropped. UDI / Product ID are identifiers and are dropped too.
"""
import os
import sys
import urllib.request
import zipfile

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend", "src"))
from shared.features import FEATURE_NAMES, build_features  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data", "raw")
CSV_PATH = os.path.join(DATA_DIR, "ai4i2020.csv")
DATASET_URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
SEED = 42

# Column names as found in the real CSV header (verified, see docs/ml-notes).
COL_TYPE = "Type"
COL_AIR = "Air temperature [K]"
COL_PROC = "Process temperature [K]"
COL_RPM = "Rotational speed [rpm]"
COL_TORQUE = "Torque [Nm]"
COL_WEAR = "Tool wear [min]"
COL_TARGET = "Machine failure"
LEAKY_COLUMNS = ["TWF", "HDF", "PWF", "OSF", "RNF"]
REQUIRED_COLUMNS = [COL_TYPE, COL_AIR, COL_PROC, COL_RPM, COL_TORQUE, COL_WEAR, COL_TARGET] + LEAKY_COLUMNS


def download_dataset(force=False):
    """Download the dataset from UCI. Raises with manual instructions on failure."""
    if os.path.exists(CSV_PATH) and not force:
        return CSV_PATH
    os.makedirs(DATA_DIR, exist_ok=True)
    zip_path = os.path.join(DATA_DIR, "ai4i.zip")
    try:
        urllib.request.urlretrieve(DATASET_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            member = next(n for n in zf.namelist() if n.endswith(".csv"))
            with zf.open(member) as src, open(CSV_PATH, "wb") as dst:
                dst.write(src.read())
    except Exception as exc:  # network, zip, or layout problems
        raise RuntimeError(
            f"Automatic download failed ({exc}). Download the dataset manually from "
            "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset "
            f"and place the CSV at {CSV_PATH}"
        ) from exc
    return CSV_PATH


def load_raw(path=None):
    path = path or download_dataset()
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {missing}. Found: {list(df.columns)}")
    return df


def clean(df):
    """Drop rows with missing/invalid values in the columns we use."""
    cols = [COL_TYPE, COL_AIR, COL_PROC, COL_RPM, COL_TORQUE, COL_WEAR, COL_TARGET]
    df = df.dropna(subset=cols).copy()
    df = df[df[COL_TYPE].isin(["L", "M", "H"])]
    return df.reset_index(drop=True)


def to_xy(df):
    """Build the feature matrix with the exact function used at inference time."""
    X = np.array([
        build_features(r[COL_AIR], r[COL_PROC], r[COL_RPM], r[COL_TORQUE], r[COL_WEAR], r[COL_TYPE])
        for _, r in df.iterrows()
    ])
    y = df[COL_TARGET].astype(int).to_numpy()
    return X, y


def split(X, y, seed=SEED):
    """Stratified 60/20/20 train/validation/test split (reproducible)."""
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.4, stratify=y, random_state=seed)
    X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5, stratify=y_tmp, random_state=seed)
    return X_tr, X_val, X_te, y_tr, y_val, y_te


__all__ = ["FEATURE_NAMES", "load_raw", "clean", "to_xy", "split", "download_dataset", "SEED"]
