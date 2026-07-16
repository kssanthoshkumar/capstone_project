"""
generate_architecture_diagram.py
=================================
Generates a PNG architecture diagram for the Network Anomaly Detection project.
Output: presentations/architecture_diagram.png

Run with:
    python generate_architecture_diagram.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

FIG_W, FIG_H = 20, 12
BG = "#0f172a"

COLORS = {
    "data":     "#3b82f6",
    "model":    "#10b981",
    "explain":  "#f97316",
    "api":      "#a78bfa",
    "ui":       "#f472b6",
    "tests":    "#64748b",
    "artifact": "#60a5fa",
    "arrow":    "#94a3b8",
    "text":     "#f1f5f9",
    "dim":      "#94a3b8",
    "title":    "#38bdf8",
}


def box(ax, x, y, w, h, color, title, subtitle=""):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.008,rounding_size=0.025",
        linewidth=1.8,
        edgecolor=color,
        facecolor=color + "28",
        zorder=2,
    )
    ax.add_patch(patch)
    cy = y + h / 2
    if subtitle:
        ax.text(x + w / 2, cy + h * 0.16, title,
                ha="center", va="center", fontsize=8, fontweight="bold",
                color=COLORS["text"], zorder=3)
        ax.text(x + w / 2, cy - h * 0.18, subtitle,
                ha="center", va="center", fontsize=6.5, color=COLORS["dim"],
                style="italic", zorder=3)
    else:
        ax.text(x + w / 2, cy, title,
                ha="center", va="center", fontsize=8, fontweight="bold",
                color=COLORS["text"], zorder=3)


def arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=COLORS["arrow"],
                                lw=1.4, mutation_scale=13),
                zorder=4)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.005, my, label, fontsize=6.5,
                color=COLORS["arrow"], va="center", zorder=5)


def section_bar(ax, x, y, w, label, color):
    ax.add_patch(plt.Rectangle((x, y), w, 0.008, color=color, alpha=0.85, zorder=2))
    ax.text(x + 0.008, y + 0.016, label, fontsize=7.5,
            fontweight="bold", color=color, va="bottom", zorder=3)


fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(0.5, 0.965, "Network Anomaly Detection  —  System Architecture",
        ha="center", fontsize=15, fontweight="bold", color=COLORS["title"])
ax.text(0.5, 0.938, "NSL-KDD · XGBoost · FastAPI · Streamlit",
        ha="center", fontsize=9, color=COLORS["dim"])

# ── Row 1: Data Pipeline  (y = 0.76) ─────────────────────────────────────────
R1_Y, R1_H = 0.76, 0.13
section_bar(ax, 0.02, R1_Y + R1_H + 0.01, 0.96, "DATA PIPELINE", COLORS["data"])

boxes_r1 = [
    (0.02,  "NSL-KDD Dataset",       "KDDTrain+ / KDDTest+\n~148k records · 41 features"),
    (0.27,  "data_loader.py",         "Auto-download & parse\nCSV → DataFrame"),
    (0.52,  "preprocessor.py",        "Dedup · IQR outlier cap\nScale · One-hot encode"),
    (0.77,  "feature_engineering.py", "Derived ratios\nPCA / UMAP reduction"),
]
BW1 = 0.22
for x, title, sub in boxes_r1:
    box(ax, x, R1_Y, BW1, R1_H, COLORS["data"], title, sub)

for i in range(len(boxes_r1) - 1):
    x1 = boxes_r1[i][0] + BW1
    x2 = boxes_r1[i + 1][0]
    arrow(ax, x1, R1_Y + R1_H / 2, x2, R1_Y + R1_H / 2)

# ── Row 2: Models + Artifacts  (y = 0.52) ────────────────────────────────────
R2_Y, R2_H = 0.52, 0.15
section_bar(ax, 0.02, R2_Y + R2_H + 0.01, 0.62, "MODEL LAYER", COLORS["model"])
section_bar(ax, 0.68, R2_Y + R2_H + 0.01, 0.30, "ARTIFACTS", COLORS["artifact"])

box(ax, 0.02, R2_Y, 0.30, R2_H, COLORS["model"],
    "Supervised Models",
    "Logistic Regression (baseline)\nRandom Forest  |  XGBoost [best]")
box(ax, 0.35, R2_Y, 0.30, R2_H, COLORS["model"],
    "Unsupervised Models",
    "Isolation Forest\nAutoencoder (reconstruction error)")
box(ax, 0.68, R2_Y, 0.30, R2_H, COLORS["artifact"],
    "Saved Artifacts",
    "preprocessor.pkl  ·  xgboost.pkl\nconfigs.yaml  ·  feature_names.json")

# feature_engineering → models
arrow(ax, 0.88, R1_Y,          0.17, R2_Y + R2_H)
arrow(ax, 0.88, R1_Y,          0.50, R2_Y + R2_H)
# supervised → artifacts
arrow(ax, 0.32, R2_Y + R2_H / 2, 0.68, R2_Y + R2_H / 2)

# ── Row 3: Explainability + API + Tests  (y = 0.28) ──────────────────────────
R3_Y, R3_H = 0.28, 0.15
section_bar(ax, 0.02, R3_Y + R3_H + 0.01, 0.38, "EXPLAINABILITY & FAIRNESS", COLORS["explain"])
section_bar(ax, 0.44, R3_Y + R3_H + 0.01, 0.30, "API LAYER  :8000", COLORS["api"])
section_bar(ax, 0.78, R3_Y + R3_H + 0.01, 0.20, "TEST SUITE", COLORS["tests"])

box(ax, 0.02, R3_Y, 0.17, R3_H, COLORS["explain"],
    "explainability.py",
    "SHAP global + local\nLIME explanations")
box(ax, 0.22, R3_Y, 0.17, R3_H, COLORS["explain"],
    "bias_audit.py",
    "Subgroup fairness\nProtocol / service slices")
box(ax, 0.44, R3_Y, 0.30, R3_H, COLORS["api"],
    "FastAPI  (app.py)",
    "GET /health\nPOST /predict  ·  POST /predict/batch")
box(ax, 0.78, R3_Y, 0.20, R3_H, COLORS["tests"],
    "37 Tests (pytest)",
    "test_api.py  (20)\ntest_preprocessor.py  (17)")

# supervised → explainability
arrow(ax, 0.17, R2_Y, 0.10, R3_Y + R3_H)
arrow(ax, 0.17, R2_Y, 0.30, R3_Y + R3_H)
# artifacts → API
arrow(ax, 0.83, R2_Y, 0.59, R3_Y + R3_H)
# API ↔ tests
ax.annotate("", xy=(0.78, R3_Y + 0.05), xytext=(0.74, R3_Y + 0.05),
            arrowprops=dict(arrowstyle="<->", color=COLORS["arrow"],
                            lw=1.2, mutation_scale=11), zorder=4)

# ── Row 4: Streamlit UI  (y = 0.07) ──────────────────────────────────────────
R4_Y, R4_H = 0.07, 0.13
section_bar(ax, 0.44, R4_Y + R4_H + 0.01, 0.54, "UI LAYER  :8501  (Streamlit)", COLORS["ui"])

box(ax, 0.44, R4_Y, 0.16, R4_H, COLORS["ui"],
    "Preset Scenarios",
    "Normal HTTP\nPort Scan · DoS Neptune")
box(ax, 0.63, R4_Y, 0.18, R4_H, COLORS["ui"],
    "Feature Form",
    "41 inputs with sliders\nand dropdowns")
box(ax, 0.84, R4_Y, 0.14, R4_H, COLORS["ui"],
    "Result Panel",
    "Label · Probability\nConfidence bar")

arrow(ax, 0.60, R4_Y + R4_H / 2, 0.63, R4_Y + R4_H / 2)
arrow(ax, 0.81, R4_Y + R4_H / 2, 0.84, R4_Y + R4_H / 2)

# API → UI  (JSON)
arrow(ax, 0.59, R3_Y, 0.59, R4_Y + R4_H, label="JSON")

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(facecolor=COLORS["data"]     + "44", edgecolor=COLORS["data"],     label="Data Pipeline"),
    mpatches.Patch(facecolor=COLORS["model"]    + "44", edgecolor=COLORS["model"],    label="Model Layer"),
    mpatches.Patch(facecolor=COLORS["explain"]  + "44", edgecolor=COLORS["explain"],  label="Explainability"),
    mpatches.Patch(facecolor=COLORS["artifact"] + "44", edgecolor=COLORS["artifact"], label="Artifacts"),
    mpatches.Patch(facecolor=COLORS["api"]      + "44", edgecolor=COLORS["api"],      label="API Layer"),
    mpatches.Patch(facecolor=COLORS["ui"]       + "44", edgecolor=COLORS["ui"],       label="UI Layer"),
    mpatches.Patch(facecolor=COLORS["tests"]    + "44", edgecolor=COLORS["tests"],    label="Tests"),
]
ax.legend(handles=legend_items, loc="lower left", bbox_to_anchor=(0.01, 0.00),
          ncol=7, framealpha=0.2, facecolor="#1e293b", edgecolor="#475569",
          labelcolor=COLORS["text"], fontsize=7.5)

OUT = Path(__file__).parent / "presentations" / "architecture_diagram.png"
OUT.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT, dpi=180, bbox_inches="tight", facecolor=BG)
print(f"Saved -> {OUT}")
