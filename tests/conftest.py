"""
conftest.py — shared fixtures for all tests.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Put src/ on sys.path so that:
#   1. Bare imports inside src/ (e.g. `from feature_engineering import ...`)
#      resolve correctly when tests import via `from src.module import ...`
#   2. Pickled objects whose class paths were saved as `preprocessor.ClassName`
#      (bare module, not `src.preprocessor`) can be deserialized by joblib.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


# ---------------------------------------------------------------------------
# Reusable payload fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def normal_record():
    """A typical normal HTTP connection (should predict 'normal')."""
    return {
        "duration": 0, "protocol_type": "tcp", "service": "http", "flag": "SF",
        "src_bytes": 232, "dst_bytes": 8153, "land": 0, "wrong_fragment": 0,
        "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 1,
        "num_compromised": 0, "root_shell": 0, "su_attempted": 0, "num_root": 0,
        "num_file_creations": 0, "num_shells": 0, "num_access_files": 0,
        "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
        "count": 8, "srv_count": 8, "serror_rate": 0.0, "srv_serror_rate": 0.0,
        "rerror_rate": 0.0, "srv_rerror_rate": 0.0, "same_srv_rate": 1.0,
        "diff_srv_rate": 0.0, "srv_diff_host_rate": 0.0, "dst_host_count": 255,
        "dst_host_srv_count": 255, "dst_host_same_srv_rate": 1.0,
        "dst_host_diff_srv_rate": 0.0, "dst_host_same_src_port_rate": 0.0,
        "dst_host_srv_diff_host_rate": 0.0, "dst_host_serror_rate": 0.0,
        "dst_host_srv_serror_rate": 0.0, "dst_host_rerror_rate": 0.0,
        "dst_host_srv_rerror_rate": 0.0,
    }


@pytest.fixture
def attack_record():
    """A port-scan / rejected-connection record (should predict 'attack')."""
    return {
        "duration": 0, "protocol_type": "tcp", "service": "private", "flag": "REJ",
        "src_bytes": 0, "dst_bytes": 0, "land": 0, "wrong_fragment": 0,
        "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 0,
        "num_compromised": 0, "root_shell": 0, "su_attempted": 0, "num_root": 0,
        "num_file_creations": 0, "num_shells": 0, "num_access_files": 0,
        "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
        "count": 229, "srv_count": 4, "serror_rate": 0.0, "srv_serror_rate": 0.0,
        "rerror_rate": 1.0, "srv_rerror_rate": 1.0, "same_srv_rate": 0.02,
        "diff_srv_rate": 0.06, "srv_diff_host_rate": 0.0, "dst_host_count": 255,
        "dst_host_srv_count": 4, "dst_host_same_srv_rate": 0.02,
        "dst_host_diff_srv_rate": 0.06, "dst_host_same_src_port_rate": 0.0,
        "dst_host_srv_diff_host_rate": 0.0, "dst_host_serror_rate": 0.0,
        "dst_host_srv_serror_rate": 0.0, "dst_host_rerror_rate": 1.0,
        "dst_host_srv_rerror_rate": 1.0,
    }
