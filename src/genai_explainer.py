"""
genai_explainer.py
==================
GenAI-powered threat explanation module (Capstone Step 9).

Uses OpenAI GPT to generate plain-English security analyst explanations
for network anomaly predictions, given the model verdict and key features.

Setup
-----
Set the OPENAI_API_KEY environment variable (see .env.example).
If the key is absent the module degrades gracefully — no exception is raised.

Usage (standalone demo)
-----------------------
    python src/genai_explainer.py

Usage (as imported module)
--------------------------
    from genai_explainer import explain_prediction
    text = explain_prediction("attack", 0.97, feature_dict)
"""

import os
from typing import Optional


# ---------------------------------------------------------------------------
# Key features used in the explanation prompt (most security-relevant subset)
# ---------------------------------------------------------------------------
_EXPLANATION_FEATURES = [
    "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes",
    "logged_in", "num_failed_logins", "root_shell", "num_compromised",
    "serror_rate", "rerror_rate",
    "count", "srv_count", "same_srv_rate", "dst_host_count",
]


def explain_prediction(
    label: str,
    probability: float,
    features: dict,
    model_name: str = "gpt-4o-mini",
) -> str:
    """Generate a plain-English SOC analyst explanation for a prediction.

    Parameters
    ----------
    label : str
        ``"attack"`` or ``"normal"``.
    probability : float
        Attack probability in [0, 1] as returned by the model.
    features : dict
        Full feature dict for the network connection record.
    model_name : str
        OpenAI model identifier.  Defaults to ``gpt-4o-mini`` (fast, cheap).

    Returns
    -------
    str
        A 2–3 sentence natural-language explanation, or a graceful fallback
        message when ``OPENAI_API_KEY`` is not set.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return (
            "AI explanation unavailable — set the OPENAI_API_KEY environment "
            "variable to enable this feature.  See .env.example for instructions."
        )

    try:
        from openai import OpenAI  # imported lazily so the module loads without openai installed

        client = OpenAI(api_key=api_key)

        feature_lines = "\n".join(
            f"  {k}: {features[k]}"
            for k in _EXPLANATION_FEATURES
            if k in features
        )

        verdict = (
            f"{'ATTACK' if label == 'attack' else 'NORMAL TRAFFIC'} "
            f"({probability:.1%} attack probability)"
        )

        prompt = (
            f"You are a senior cybersecurity analyst reviewing a network intrusion detection alert.\n\n"
            f"The ML model classified this connection as: {verdict}\n\n"
            f"Key connection features:\n{feature_lines}\n\n"
            f"In 2–3 sentences explain in plain English:\n"
            f"1. What this traffic pattern suggests about the connection.\n"
            f"2. Which specific features are most suspicious or reassuring.\n"
            f"3. What action the SOC analyst should take.\n\n"
            f"Be direct and concise. Do not mention machine learning or model internals."
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as exc:  # network error, quota exceeded, etc.
        return f"AI explanation unavailable: {exc}"


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    dos_attack = {
        "protocol_type": "tcp", "service": "http", "flag": "S0",
        "src_bytes": 0, "dst_bytes": 0, "logged_in": 0,
        "num_failed_logins": 0, "root_shell": 0, "num_compromised": 0,
        "serror_rate": 1.0, "rerror_rate": 0.0,
        "count": 511, "srv_count": 511, "same_srv_rate": 1.0,
        "dst_host_count": 255,
    }

    normal_http = {
        "protocol_type": "tcp", "service": "http", "flag": "SF",
        "src_bytes": 232, "dst_bytes": 8153, "logged_in": 1,
        "num_failed_logins": 0, "root_shell": 0, "num_compromised": 0,
        "serror_rate": 0.0, "rerror_rate": 0.0,
        "count": 8, "srv_count": 8, "same_srv_rate": 1.0,
        "dst_host_count": 255,
    }

    print("=== Example 1: DoS Attack ===")
    print(explain_prediction("attack", 0.998, dos_attack))
    print()
    print("=== Example 2: Normal HTTP Traffic ===")
    print(explain_prediction("normal", 0.004, normal_http))
