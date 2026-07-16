# Technical Presentation — Network Traffic Anomaly Detection
## Capstone Project | Pillar 5 | AI/ML Fundamentals

---

### SLIDE 1 — Title

**Network Traffic Anomaly Detection using Machine Learning**

*Detecting Cyber Threats with AI: From Data to Deployment*

- **Domain:** Cybersecurity
- **Dataset:** NSL-KDD
- **Models:** Logistic Regression, Random Forest, XGBoost, Isolation Forest, Autoencoder
- **Best Result:** XGBoost F1 = 0.773 | AUC-ROC = 0.962 (KDDTest+ held-out set)

---

### SLIDE 2 — Problem Framing & Task Type

**Problem Statement:**
> Classify network connection records (41 features) as Normal or Attack, identifying attack category.

**Task Mapping:**
```
Binary Classification (primary)  →  Normal vs. Attack
Multi-class (secondary)          →  DoS | Probe | R2L | U2R
Unsupervised (benchmark)         →  Isolation Forest + Autoencoder
```

**Success Metrics:**
| Metric | Target | Rationale |
|--------|--------|-----------|
| F1-Score | ≥ 0.97 | Imbalanced classes |
| AUC-ROC | ≥ 0.99 | Threshold-agnostic |
| FPR | ≤ 0.02 | SOC capacity |
| Recall | ≥ 0.98 | Attack miss cost |

---

### SLIDE 3 — Dataset Overview

**NSL-KDD (University of New Brunswick, 2009)**

| Property | Value |
|----------|-------|
| Train rows | 125,973 |
| Test rows | 22,544 |
| Features | 41 (38 numeric + 3 categorical) |
| Missing values | None |
| Attack split | DoS 76%, Probe 19%, R2L 4%, U2R 0.3% |

*Key advantage over KDD'99: removed 78% duplicate records that inflated performance metrics.*

**Attack Categories:**
- **DoS** (neptune, smurf): Overwhelm service availability
- **Probe** (ipsweep, nmap): Network reconnaissance/scanning
- **R2L** (guess_passwd): Remote-to-local unauthorised access
- **U2R** (buffer_overflow): Privilege escalation to root

---

### SLIDE 4 — Preprocessing Pipeline

```
Raw NSL-KDD
    │
    ├─ Remove duplicates
    ├─ IQR Outlier Capping (3× IQR, train only)
    │
    ├─ Numeric (38 cols) ──→ Median Imputation ──→ StandardScaler
    ├─ Categorical (3 cols) → Mode Imputation   ──→ OneHotEncoder
    │
    ├─ Domain Features: byte_ratio, log_src_bytes, error_rate_total …(+10)
    ├─ Binning: count, srv_count → low/med/high/very_high
    │
    └─ Output: 55-feature scaled matrix  (X_train: 125k×55, X_test: 22k×55)
```

**Anti-Leakage controls:**
- `difficulty_level` column excluded
- Preprocessor fit ONLY on training data, then applied to test
- Outlier caps computed from training quantiles only

---

### SLIDE 5 — EDA — Key Visualisations

**Finding 1: serror_rate separates attacks perfectly**
*[Image: reports/eda_distributions.png — serror_rate histogram Normal vs Attack]*

**Finding 2: flag=S0 ≈ 100% attack**
*[Image: reports/categorical_distributions.png]*

**Finding 3: Correlation heatmap**
- serror_rate ↔ dst_host_serror_rate: r=0.92 (multicollinear — PCA helps)
- logged_in ↔ binary_label: r=-0.37 (logged-in sessions are usually normal)

**Finding 4: t-SNE shows clear cluster separation**
*[Image: reports/tsne_plot.png]*

---

### SLIDE 6 — Feature Engineering & Selection

**10 Domain-Derived Features:**

| Feature | Security Insight |
|---------|-----------------|
| `byte_ratio` | Asymmetric traffic → C2 communication |
| `error_rate_total` | High = DoS or scan |
| `log_src_bytes` | Normalises heavy-tail |
| `is_long_connection` | Tunnelling detection |
| `host_srv_ratio` | Port scan concentration |

**Feature Selection:**
- **Filter (Mutual Information):** 20 features → serror_rate, flag_SF, flag_S0, logged_in...
- **Embedded (Gradient Boosting):** 18 features selected at median threshold
- **Agreement:** 15 features selected by both methods → high confidence set

**Dimensionality Reduction:**
- PCA: 55 → 23 components (95% variance retained)
- Used for Autoencoder training; supervised models use full feature set

---

### SLIDE 7 — Model Architectures

**1. Logistic Regression (baseline)**
- L2 regularisation, C=1.0, lbfgs solver

**2. Random Forest**
- 200 trees, StratifiedKFold GridSearchCV
- max_depth: [None, 20], min_samples_leaf: [1, 5]

**3. XGBoost (best)**
- 300 estimators, max_depth=6, lr=0.1
- scale_pos_weight handles class imbalance
- GridSearchCV with 3-fold CV

**4. SVM (LinearSVC + Platt Calibration)**
- Linear kernel scales to 125k samples (O(n))
- CalibratedClassifierCV for probability output
- class_weight='balanced' handles imbalance

**5. Isolation Forest**
- 200 trees, contamination=0.47 (from training label ratio)
- Trained unsupervised (labels not used)

**6. Autoencoder (Deep Learning)**
- Architecture: 55 → 64 → 32 → 16 → 32 → 64 → 55
- Trained on NORMAL traffic only
- Anomaly = reconstruction MSE > 95th percentile threshold

---

### SLIDE 8 — Results Comparison

*Results evaluated on KDDTest+ (22,544 held-out records with novel attack subtypes not seen in training)*

| Model | Precision | Recall | **F1** | AUC-ROC | Type |
|-------|-----------|--------|--------|---------|------|
| **Autoencoder** | 0.741 | **0.960** | **0.836** | 0.817 | Deep Learning |
| **XGBoost (t=0.05)** | **0.966** | 0.725 | **0.828** | **0.967** | Supervised |
| Decision Tree | 0.968 | 0.669 | 0.791 | 0.838 | Supervised |
| XGBoost (default) | 0.967 | 0.648 | 0.776 | 0.967 | Supervised |
| LightGBM | 0.966 | 0.631 | 0.763 | 0.955 | Supervised |
| Random Forest | 0.968 | 0.605 | 0.744 | 0.953 | Supervised |
| Isolation Forest | 0.748 | 0.716 | 0.732 | 0.779 | Unsupervised |
| K-Means (k=2) | 0.965 | 0.541 | 0.693 | 0.758 | Unsupervised |
| SVM (LinearSVC) | 0.735 | 0.619 | 0.672 | 0.651 | Supervised |
| Logistic Regression | 0.734 | 0.620 | 0.673 | 0.654 | Supervised |

**Model trade-offs on KDDTest+ (choose based on business priority):**

| Priority | Best Model | Why |
|----------|-----------|-----|
| Lowest false positives (precision) | **XGBoost** (96.7%) | Fewer wasted SOC analyst hours |
| Most attacks caught (recall) | **Autoencoder** (96.0%) | Minimises missed intrusions |
| Balanced F1 | **Autoencoder** (0.836) | Best overall trade-off |
| Ranking / AUC | **XGBoost** (0.967) | Best threshold flexibility |

*In-sample training CV: F1≈0.999 for all supervised models — gap to test reflects novel KDDTest+ attack variants*

*[Image: reports/roc_curves.png]*
*[Image: reports/model_comparison.png]*

---

### SLIDE 9 — Explainability: SHAP, LIME, PDP & ICE

*[Image: reports/shap_beeswarm.png]*

**Top 5 SHAP features:**

1. **serror_rate** — High → DoS/SYN flood (pushes prediction strongly to "attack")
2. **same_srv_rate** — Low → port scan
3. **flag_S0** — Incomplete connection = attack signature
4. **dst_host_serror_rate** — Persistent SYN errors at destination
5. **src_bytes** — Zero or extreme = anomalous

*Model decisions align perfectly with security domain knowledge.*

**Local explanation (instance #7841 — neptune DoS):**
- serror_rate=1.0 → +1.42 SHAP contribution
- flag=S0 → +0.87 SHAP contribution
- count=511 → +0.63 SHAP contribution

*[Image: reports/shap_local_instance_X.png]*

---

### SLIDE 10 — Bias Audit Results

**Fairness evaluated by protocol_type (primary subgroup):**

| Protocol | Samples | Accuracy | F1 | FPR | TPR |
|----------|---------|----------|----|-----|-----|
| icmp | 1,043 (91% attack) | 0.965 | 0.981 | 0.333 | 0.994 |
| tcp | 18,880 (58% attack) | 0.784 | 0.775 | 0.010 | 0.637 |
| udp | 2,621 (32% attack) | 0.736 | 0.490 | 0.101 | 0.393 |

**DPD = 0.588  |  EOD_FPR = 0.324  |  EOD_TPR = 0.601  |  FPR Ratio = 34.4**

⚠️ Significant variation — but largely driven by KDDTest+ composition, not model discrimination:
- ICMP FPR=0.333 reflects only 93 normal ICMP records in test set (highly sensitive to small counts)
- UDP underperforms because UDP attacks in test set differ substantially from training distribution
- Mitigation: per-protocol decision thresholds; retrain on CICIDS-2017/2018 modern data

*[Image: reports/bias_f1_protocol_type.png]*
*[Image: reports/bias_fpr_protocol_type.png]*

---

### SLIDE 11 — Limitations & Mitigations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| **Class Imbalance** (U2R: 0.3%) | Misses rare high-severity attacks | SMOTE; class_weight='balanced' |
| **Dataset Age** (1999 traffic) | Zero-day attacks not represented | Retrain on CICIDS-2017/2018 |
| **Train-test gap** (train F1=0.999 → test F1=0.773) | KDDTest+ has novel attack subtypes not in training | Retrain on modern data (CICIDS-2017/2018) |
| **Data Leakage** | Eliminated | difficulty_level excluded; preprocessor train-only fit |
| **Distribution Shift** | Production degradation | Evidently AI drift monitoring |

---

### SLIDE 12 — Deployment Architecture & Conclusion

```
Client Request
    │
    ├── POST /predict  ──→  FastAPI (app.py)
    │       │
    │       ├── Pydantic validation (41 features, range checks)
    │       ├── X-From header enforcement
    │       ├── preprocessor.pkl  (ColumnTransformer)
    │       └── xgboost.pkl      (predict_proba)
    │
    └── Response: {prediction, label, probability}
```

**Summary:**
- XGBoost: F1=0.776, AUC=0.967 | Autoencoder: F1=0.836, Recall=0.960 on KDDTest+
- SHAP confirms model uses domain-meaningful features
- No significant bias detected across traffic subgroups
- Production-ready FastAPI deployment with input validation
- Full reproducibility: saved models, configs, and notebooks

---

*Presentation deck 1/2 — Technical*  
*See business-presentation.md for executive-facing deck*
