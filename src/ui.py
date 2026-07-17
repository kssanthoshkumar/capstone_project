"""
ui.py
=====
Streamlit UI for the Network Anomaly Detection model.

Run with:
    streamlit run src/ui.py
"""

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # load OPENAI_API_KEY from .env if present

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Network Anomaly Detector",
    page_icon="🛡️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Load model artifacts (cached so they only load once)
# ---------------------------------------------------------------------------
MODEL_DIR = Path(__file__).parent.parent / "models"


@st.cache_resource
def load_artifacts():
    preprocessor = joblib.load(MODEL_DIR / "preprocessor.pkl")
    model = joblib.load(MODEL_DIR / "xgboost.pkl")
    return preprocessor, model


preprocessor, model = load_artifacts()

# ---------------------------------------------------------------------------
# Preset traffic scenarios
# ---------------------------------------------------------------------------
PRESETS = {
    "Normal HTTP Traffic": {
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
    },
    "Port Scan Attack": {
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
    },
    "DoS Attack (Neptune)": {
        "duration": 0, "protocol_type": "tcp", "service": "http", "flag": "S0",
        "src_bytes": 0, "dst_bytes": 0, "land": 0, "wrong_fragment": 0,
        "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 0,
        "num_compromised": 0, "root_shell": 0, "su_attempted": 0, "num_root": 0,
        "num_file_creations": 0, "num_shells": 0, "num_access_files": 0,
        "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
        "count": 511, "srv_count": 511, "serror_rate": 1.0, "srv_serror_rate": 1.0,
        "rerror_rate": 0.0, "srv_rerror_rate": 0.0, "same_srv_rate": 1.0,
        "diff_srv_rate": 0.0, "srv_diff_host_rate": 0.0, "dst_host_count": 255,
        "dst_host_srv_count": 255, "dst_host_same_srv_rate": 1.0,
        "dst_host_diff_srv_rate": 0.0, "dst_host_same_src_port_rate": 1.0,
        "dst_host_srv_diff_host_rate": 0.0, "dst_host_serror_rate": 1.0,
        "dst_host_srv_serror_rate": 1.0, "dst_host_rerror_rate": 0.0,
        "dst_host_srv_rerror_rate": 0.0,
    },
}

PROTOCOL_TYPES = ["tcp", "udp", "icmp"]
SERVICES = [
    "http", "ftp", "smtp", "ssh", "dns", "ftp_data", "mtp", "finger", "telnet",
    "pop_3", "imap4", "nntp", "netbios_ns", "netbios_dgm", "netbios_ssn", "IRC",
    "domain_u", "private", "auth", "http_443", "other",
]
FLAGS = ["SF", "S0", "S1", "S2", "S3", "OTH", "REJ", "RSTO", "RSTOS0", "RSTR", "SH"]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🛡️ Network Anomaly Detection")
st.markdown(
    "Powered by **XGBoost** trained on the NSL-KDD dataset · "
    "Detects intrusions, DoS, port scans, and other malicious traffic."
)
st.divider()

# ---------------------------------------------------------------------------
# Sidebar — preset loader
# ---------------------------------------------------------------------------
st.sidebar.header("Quick Presets")
st.sidebar.markdown("Load a pre-filled example scenario:")

selected_preset = st.sidebar.selectbox("Choose a preset", ["(custom)"] + list(PRESETS.keys()))

if selected_preset != "(custom)":
    defaults = PRESETS[selected_preset]
else:
    defaults = PRESETS["Normal HTTP Traffic"]  # fallback defaults

st.sidebar.divider()
st.sidebar.markdown("**About**")
st.sidebar.markdown(
    "This app classifies network connection records as **normal** or **attack** "
    "using a model trained on ~126k NSL-KDD samples.\n\n"
    "F1-Score: **0.99** · AUC-ROC: **0.999**"
)

# ---------------------------------------------------------------------------
# Feature input form
# ---------------------------------------------------------------------------
with st.form("prediction_form"):
    st.subheader("Connection Features")

    col1, col2, col3 = st.columns(3)

    # --- Basic ---
    with col1:
        st.markdown("**Basic**")
        duration       = st.number_input("duration", min_value=0.0, value=float(defaults["duration"]))
        protocol_type  = st.selectbox("protocol_type", PROTOCOL_TYPES,
                                      index=PROTOCOL_TYPES.index(defaults["protocol_type"]))
        service        = st.selectbox("service", SERVICES,
                                      index=SERVICES.index(defaults["service"]) if defaults["service"] in SERVICES else 0)
        flag           = st.selectbox("flag", FLAGS,
                                      index=FLAGS.index(defaults["flag"]) if defaults["flag"] in FLAGS else 0)
        src_bytes      = st.number_input("src_bytes", min_value=0.0, value=float(defaults["src_bytes"]))
        dst_bytes      = st.number_input("dst_bytes", min_value=0.0, value=float(defaults["dst_bytes"]))
        land           = st.selectbox("land", [0, 1], index=int(defaults["land"]))
        wrong_fragment = st.number_input("wrong_fragment", min_value=0.0, value=float(defaults["wrong_fragment"]))
        urgent         = st.number_input("urgent", min_value=0.0, value=float(defaults["urgent"]))

    # --- Content ---
    with col2:
        st.markdown("**Content**")
        hot               = st.number_input("hot", min_value=0.0, value=float(defaults["hot"]))
        num_failed_logins = st.number_input("num_failed_logins", min_value=0.0, value=float(defaults["num_failed_logins"]))
        logged_in         = st.selectbox("logged_in", [0, 1], index=int(defaults["logged_in"]))
        num_compromised   = st.number_input("num_compromised", min_value=0.0, value=float(defaults["num_compromised"]))
        root_shell        = st.selectbox("root_shell", [0, 1], index=int(defaults["root_shell"]))
        su_attempted      = st.selectbox("su_attempted", [0, 1], index=int(defaults["su_attempted"]))
        num_root          = st.number_input("num_root", min_value=0.0, value=float(defaults["num_root"]))
        num_file_creations = st.number_input("num_file_creations", min_value=0.0, value=float(defaults["num_file_creations"]))
        num_shells        = st.number_input("num_shells", min_value=0.0, value=float(defaults["num_shells"]))
        num_access_files  = st.number_input("num_access_files", min_value=0.0, value=float(defaults["num_access_files"]))
        num_outbound_cmds = st.number_input("num_outbound_cmds", min_value=0.0, value=float(defaults["num_outbound_cmds"]))
        is_host_login     = st.selectbox("is_host_login", [0, 1], index=int(defaults["is_host_login"]))
        is_guest_login    = st.selectbox("is_guest_login", [0, 1], index=int(defaults["is_guest_login"]))

    # --- Traffic & Host ---
    with col3:
        st.markdown("**Traffic & Host-based**")
        count              = st.number_input("count", min_value=0.0, value=float(defaults["count"]))
        srv_count          = st.number_input("srv_count", min_value=0.0, value=float(defaults["srv_count"]))
        serror_rate        = st.slider("serror_rate", 0.0, 1.0, float(defaults["serror_rate"]))
        srv_serror_rate    = st.slider("srv_serror_rate", 0.0, 1.0, float(defaults["srv_serror_rate"]))
        rerror_rate        = st.slider("rerror_rate", 0.0, 1.0, float(defaults["rerror_rate"]))
        srv_rerror_rate    = st.slider("srv_rerror_rate", 0.0, 1.0, float(defaults["srv_rerror_rate"]))
        same_srv_rate      = st.slider("same_srv_rate", 0.0, 1.0, float(defaults["same_srv_rate"]))
        diff_srv_rate      = st.slider("diff_srv_rate", 0.0, 1.0, float(defaults["diff_srv_rate"]))
        srv_diff_host_rate = st.slider("srv_diff_host_rate", 0.0, 1.0, float(defaults["srv_diff_host_rate"]))
        dst_host_count     = st.number_input("dst_host_count", min_value=0.0, value=float(defaults["dst_host_count"]))
        dst_host_srv_count = st.number_input("dst_host_srv_count", min_value=0.0, value=float(defaults["dst_host_srv_count"]))
        dst_host_same_srv_rate      = st.slider("dst_host_same_srv_rate", 0.0, 1.0, float(defaults["dst_host_same_srv_rate"]))
        dst_host_diff_srv_rate      = st.slider("dst_host_diff_srv_rate", 0.0, 1.0, float(defaults["dst_host_diff_srv_rate"]))
        dst_host_same_src_port_rate = st.slider("dst_host_same_src_port_rate", 0.0, 1.0, float(defaults["dst_host_same_src_port_rate"]))
        dst_host_srv_diff_host_rate = st.slider("dst_host_srv_diff_host_rate", 0.0, 1.0, float(defaults["dst_host_srv_diff_host_rate"]))
        dst_host_serror_rate        = st.slider("dst_host_serror_rate", 0.0, 1.0, float(defaults["dst_host_serror_rate"]))
        dst_host_srv_serror_rate    = st.slider("dst_host_srv_serror_rate", 0.0, 1.0, float(defaults["dst_host_srv_serror_rate"]))
        dst_host_rerror_rate        = st.slider("dst_host_rerror_rate", 0.0, 1.0, float(defaults["dst_host_rerror_rate"]))
        dst_host_srv_rerror_rate    = st.slider("dst_host_srv_rerror_rate", 0.0, 1.0, float(defaults["dst_host_srv_rerror_rate"]))

    submitted = st.form_submit_button("🔍 Analyse Traffic", use_container_width=True, type="primary")

# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
if submitted:
    record = {
        "duration": duration, "protocol_type": protocol_type, "service": service,
        "flag": flag, "src_bytes": src_bytes, "dst_bytes": dst_bytes, "land": land,
        "wrong_fragment": wrong_fragment, "urgent": urgent, "hot": hot,
        "num_failed_logins": num_failed_logins, "logged_in": logged_in,
        "num_compromised": num_compromised, "root_shell": root_shell,
        "su_attempted": su_attempted, "num_root": num_root,
        "num_file_creations": num_file_creations, "num_shells": num_shells,
        "num_access_files": num_access_files, "num_outbound_cmds": num_outbound_cmds,
        "is_host_login": is_host_login, "is_guest_login": is_guest_login,
        "count": count, "srv_count": srv_count, "serror_rate": serror_rate,
        "srv_serror_rate": srv_serror_rate, "rerror_rate": rerror_rate,
        "srv_rerror_rate": srv_rerror_rate, "same_srv_rate": same_srv_rate,
        "diff_srv_rate": diff_srv_rate, "srv_diff_host_rate": srv_diff_host_rate,
        "dst_host_count": dst_host_count, "dst_host_srv_count": dst_host_srv_count,
        "dst_host_same_srv_rate": dst_host_same_srv_rate,
        "dst_host_diff_srv_rate": dst_host_diff_srv_rate,
        "dst_host_same_src_port_rate": dst_host_same_src_port_rate,
        "dst_host_srv_diff_host_rate": dst_host_srv_diff_host_rate,
        "dst_host_serror_rate": dst_host_serror_rate,
        "dst_host_srv_serror_rate": dst_host_srv_serror_rate,
        "dst_host_rerror_rate": dst_host_rerror_rate,
        "dst_host_srv_rerror_rate": dst_host_srv_rerror_rate,
    }

    df = pd.DataFrame([record])
    X = preprocessor.transform(df)
    prob = float(model.predict_proba(X)[0, 1])
    pred = int(prob >= 0.5)
    label = "attack" if pred == 1 else "normal"

    st.divider()
    st.subheader("Prediction Result")

    res_col1, res_col2, res_col3 = st.columns(3)

    with res_col1:
        if pred == 1:
            st.error(f"⚠️ **ATTACK DETECTED**")
        else:
            st.success(f"✅ **NORMAL TRAFFIC**")

    with res_col2:
        st.metric("Attack Probability", f"{prob:.2%}")

    with res_col3:
        confidence = prob if pred == 1 else (1 - prob)
        st.metric("Model Confidence", f"{confidence:.2%}")

    st.progress(prob, text=f"Attack probability: {prob:.2%}")

    # ------------------------------------------------------------------
    # GenAI Analyst Explanation (Step 9)
    # ------------------------------------------------------------------
    st.divider()
    with st.expander("🤖 AI Analyst Explanation", expanded=pred == 1):
        if os.environ.get("LOCAL_LLM_URL") or os.environ.get("OPENAI_API_KEY"):
            with st.spinner("Generating analyst explanation..."):
                sys.path.insert(0, str(Path(__file__).parent))
                from genai_explainer import explain_prediction
                explanation = explain_prediction(label, prob, record)
            st.info(explanation)
        else:
            st.warning(
                "No LLM backend configured. Set `LOCAL_LLM_URL` (llama.cpp / LM Studio / Ollama) "
                "or `OPENAI_API_KEY` in your `.env` file. See `.env.example` for setup instructions."
            )
