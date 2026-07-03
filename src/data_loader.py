"""
data_loader.py
==============
Utilities for downloading and loading the NSL-KDD dataset.

Dataset source:
    https://www.unb.ca/cic/datasets/nsl.html
    KDDTrain+.txt / KDDTest+.txt  (the enhanced, duplicate-free version of KDD Cup 1999)
"""

import os
import logging
import requests
from pathlib import Path

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Column names per NSL-KDD documentation
COLUMN_NAMES = [
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
    "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "su_attempted", "num_root", "num_file_creations",
    "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label", "difficulty_level"
]

# Attack category mapping (multi-class)
ATTACK_CATEGORY_MAP = {
    "normal": "normal",
    # DoS
    "back": "dos", "land": "dos", "neptune": "dos", "pod": "dos",
    "smurf": "dos", "teardrop": "dos", "apache2": "dos", "udpstorm": "dos",
    "processtable": "dos", "worm": "dos",
    # Probe
    "ipsweep": "probe", "nmap": "probe", "portsweep": "probe",
    "satan": "probe", "mscan": "probe", "saint": "probe",
    # R2L
    "ftp_write": "r2l", "guess_passwd": "r2l", "imap": "r2l",
    "multihop": "r2l", "phf": "r2l", "spy": "r2l", "warezclient": "r2l",
    "warezmaster": "r2l", "sendmail": "r2l", "named": "r2l",
    "snmpgetattack": "r2l", "snmpguess": "r2l", "xlock": "r2l",
    "xsnoop": "r2l", "httptunnel": "r2l",
    # U2R
    "buffer_overflow": "u2r", "loadmodule": "u2r", "perl": "u2r",
    "rootkit": "u2r", "mailbomb": "u2r", "ps": "u2r",
    "sqlattack": "u2r", "xterm": "u2r",
}

# Mirrors for NSL-KDD (public GitHub mirrors)
DATASET_URLS = {
    "train": "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain+.txt",
    "test":  "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest+.txt",
}


def download_dataset(data_dir: str = "data/raw") -> None:
    """Download NSL-KDD train/test files if not already present."""
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    for split, url in DATASET_URLS.items():
        dest = data_path / f"KDD{'Train' if split == 'train' else 'Test'}+.txt"
        if dest.exists():
            logger.info("File already exists: %s — skipping download.", dest)
            continue
        logger.info("Downloading %s dataset from %s …", split, url)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        dest.write_bytes(response.content)
        logger.info("Saved to %s", dest)


def load_raw(path: str) -> pd.DataFrame:
    """Load a raw NSL-KDD text file into a DataFrame."""
    df = pd.read_csv(path, header=None, names=COLUMN_NAMES)
    return df


def load_dataset(
    data_dir: str = "data/raw",
    auto_download: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load train and test splits of NSL-KDD.

    Returns
    -------
    (train_df, test_df) — raw DataFrames with original labels preserved.
    """
    train_path = Path(data_dir) / "KDDTrain+.txt"
    test_path  = Path(data_dir) / "KDDTest+.txt"

    if auto_download and (not train_path.exists() or not test_path.exists()):
        download_dataset(data_dir)

    train_df = load_raw(str(train_path))
    test_df  = load_raw(str(test_path))

    # Add binary label: 0 = normal, 1 = attack
    train_df["binary_label"] = (train_df["label"] != "normal").astype(int)
    test_df["binary_label"]  = (test_df["label"]  != "normal").astype(int)

    # Add attack category
    train_df["attack_category"] = train_df["label"].map(ATTACK_CATEGORY_MAP).fillna("unknown")
    test_df["attack_category"]  = test_df["label"].map(ATTACK_CATEGORY_MAP).fillna("unknown")

    logger.info(
        "Loaded train=%d rows, test=%d rows | Features=%d",
        len(train_df), len(test_df), len(train_df.columns),
    )
    return train_df, test_df


def dataset_summary(df: pd.DataFrame) -> dict:
    """Return a concise summary dictionary of a DataFrame."""
    return {
        "shape": df.shape,
        "dtypes": df.dtypes.value_counts().to_dict(),
        "missing_values": df.isnull().sum().sum(),
        "duplicate_rows": df.duplicated().sum(),
        "label_distribution": df["binary_label"].value_counts(normalize=True).round(4).to_dict()
        if "binary_label" in df.columns else {},
    }
