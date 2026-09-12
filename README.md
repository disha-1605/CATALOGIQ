# CatalogIQ — Product Intelligence & Catalog Diagnostic Engine

> **Disclaimer**: This prototype uses synthetic/demo fashion catalog and search data. It does not use private Myntra data or claim to represent Myntra's production systems. Business impact figures are modeled estimates, not observed production metrics.

---

## 1. What CatalogIQ Solves

CatalogIQ is an internal product-intelligence engine for fashion e-commerce that identifies high-demand customer search queries failing due to catalog metadata deficiencies. By deterministically matching search intent against catalog attributes, it diagnoses whether search friction is caused by missing product tags (`ATTRIBUTE_GAP`) or catalog depth shortages (`INVENTORY_GAP`), ranking issues by revenue opportunity so catalog teams know what to fix first.

---

## 2. Product Flow Diagram

```
Customer Search Query
   │
   ▼
Search Performance Analysis (CTR / CVR)
   │
   ▼
Query Intent Extraction (Deterministic Fashion Vocabulary)
   │
   ▼
Search-to-Product Matching (Relevant vs Correctly Matching)
   │
   ▼
Catalog Coverage Calculation (N_correct / N_relevant)
   │
   ▼
Root Cause Diagnostic Engine
   ├── [N_relevant < 4]                   ──► INVENTORY_GAP
   ├── [N_relevant >= 4 & Coverage < 60%] ──► ATTRIBUTE_GAP
   └── [Coverage >= 60%]                  ──► NO_CATALOG_GAP_DETECTED
   │
   ▼
Opportunity Scoring (0–100: Demand + Friction + Gap + Fixability)
   │
   ▼
Executive PM Explanation (LLM / Deterministic Fallback) & Recommended Action
```

---

## 3. Architecture Overview

```
CatalogIQ/
├── backend/
│   ├── main.py                  # FastAPI application & REST routing
│   ├── database.py              # SQLite + SQLAlchemy session setup
│   ├── models.py                # Database models for Product & SearchQuery
│   ├── schemas.py               # Pydantic v2 schemas for responses & requests
│   ├── scoring.py               # Catalog Health Score & Classification (0-100)
│   ├── catalog_analyzer.py      # Fashion vocabulary intent & product matcher
│   ├── search_analyzer.py       # CTR/CVR math, coverage & root cause engine
│   ├── opportunity.py           # Multi-factor Opportunity Score engine (0-100)
│   ├── llm_explainer.py         # Plain-language explanation engine & fallback
│   ├── evaluate.py              # Standalone evaluation & precision/recall script
│   ├── seed_data.py             # Reproducible synthetic dataset generator (seed=42)
│   ├── data/
│   │   ├── products.csv         # 200 synthetic products with controlled defects
│   │   └── searches.csv         # 40 synthetic search queries with traffic metrics
│   └── tests/
│       ├── __init__.py
│       └── test_core_logic.py   # 24 unit, edge-case, and API integration tests
├── .env.example                 # Environment variable templates
├── .gitignore                   # Version control ignore definitions
├── Procfile                     # Deployment process config (Render/Railway)
├── requirements.txt             # Pinned backend dependencies
└── README.md                    # System documentation & usage guide
```

---

## 4. Dataset Assumptions

- **Synthetic Fashion Catalog (~200 items)**: Synthetically generated across 10 realistic Indian fashion categories (*Kurtas, Shirts, Jeans, Dresses, Sneakers, Running Shoes, Jackets, T-shirts, Trousers, Handbags*), covering brands such as FabIndia, Manyavar, Roadster, HRX, and Allen Solly.
- **Controlled Defects**: Contains deterministic catalog imperfections including omitted fit tags on oversized items (`fit = NULL`), missing material/sleeve tags, brief titles, and short descriptions.
- **Search Queries (~40 items)**: Contains high-demand, long-tail, and healthy search queries with realistic search volume (impressions), clicks, and orders.
- **Mathematical Connection**:
  $$\text{CTR} = \frac{\text{Clicks}}{\text{Impressions}}, \quad \text{CVR} = \frac{\text{Orders}}{\text{Clicks}}$$

---

## 5. Scoring Methodology

### 5.1. Catalog Health Score (0–100)
Evaluates individual catalog products deterministically across 4 configurable dimensions:

$$\text{Health Score} = 0.40 \times \text{Completeness} + 0.25 \times \text{Title Quality} + 0.20 \times \text{Desc Quality} + 0.15 \times \text{Consistency}$$

- **Attribute Completeness (40%)**: Populated ratio of required schema attributes (`brand`, `gender`, `color`, `material`, `price`, `fit`, `sleeve`, `pattern`).
- **Title Quality (25%)**: Evaluates title length (20–80 chars), brand presence (+20), category keyword (+25), gender (+10), and descriptive attribute modifiers (+15).
- **Description Quality (20%)**: Evaluates description length (>60 chars), material mentions (+20), styling guidance (+20), and wash care (+20).
- **Category Consistency (15%)**: Assesses keyword alignment between title/description and assigned category.

**Health Classification Tiers:**
- `85 – 100`: **Excellent**
- `70 – 84`: **Good**
- `50 – 69`: **Needs Attention**
- `0 – 49`: **Critical**

---

### 5.2. Opportunity Score (0–100)
Ranks search friction to guide PM and catalog operations prioritization:

$$\text{Opportunity Score} = \text{round}(0.40 \times \text{Demand} + 0.30 \times \text{Friction} + 0.20 \times \text{Gap} + 0.10 \times \text{Fixability}, 1)$$

- **Demand Score (40%)**: Normalized search volume across the dataset ($0–100$).
- **Search Friction Score (30%)**: Normalized metric reflecting low CTR and low CVR relative to dataset benchmarks ($0–100$).
- **Catalog Gap Score (20%)**: $(1.0 - \text{Coverage}) \times 100$.
- **Fixability Score (10%)**:
  - `ATTRIBUTE_GAP` $\rightarrow 95.0$ (Fast catalog metadata enrichment, high ROI)
  - `INVENTORY_GAP` $\rightarrow 35.0$ (Procurement / supplier onboarding required)
  - `NO_CATALOG_GAP_DETECTED` $\rightarrow 10.0$ (Already healthy)

---

## 6. Root-Cause Logic & Thresholds

| Root Cause | Condition | Meaning |
| :--- | :--- | :--- |
| `INVENTORY_GAP` | $N_{relevant} < 4$ | Customer demand exists, but active catalog lacks inventory depth in category/gender. |
| `ATTRIBUTE_GAP` | $N_{relevant} \ge 4 \text{ and } \text{Coverage} < 0.60$ | Adequate relevant products exist in catalog, but missing/inconsistent attributes prevent discovery. |
| `NO_CATALOG_GAP_DETECTED` | $N_{relevant} \ge 4 \text{ and } \text{Coverage} \ge 0.60$ | Healthy catalog coverage and inventory availability. |

---

## 7. Evaluation Results

Results generated by `backend/evaluate.py` comparing ground-truth design labels against the deterministic engine output on the 40-query dataset:

```
===========================================================================
CatalogIQ — Deterministic Root Cause Engine Evaluation
===========================================================================
Total Evaluated Queries : 40
Correct Predictions     : 30
Overall Accuracy        : 75.0%

---------------------------------------------------------------------------
Class                      | Precision  | Recall     | F1-Score   | Support 
---------------------------------------------------------------------------
ATTRIBUTE_GAP              |     63.16% |     85.71% |     72.73% |      14
INVENTORY_GAP              |     91.67% |     84.62% |     88.00% |      13
NO_CATALOG_GAP_DETECTED    |     77.78% |     53.85% |     63.64% |      13
---------------------------------------------------------------------------

Confusion Matrix (Rows: Ground Truth, Columns: Predicted):
                           | Attr Gap   | Inv Gap    | No Gap    
-----------------------------------------------------------------
ATTRIBUTE_GAP              |         12 |          1 |          1
INVENTORY_GAP              |          1 |         11 |          1
NO_CATALOG_GAP_DETECTED    |          6 |          0 |          7
-----------------------------------------------------------------
```

### Analysis of Misclassifications:
1. **Color Multiplicity vs Coverage Threshold**: In queries intended as healthy (e.g., `'formal white shirt men'`, `'casual blue shirt men'`), the synthetic catalog distributes shirts across 13 distinct color variants. Because white shirts constitute 50% of the formal shirt stock (rather than $\ge 60\%$), the strict $\text{Coverage} < 60\%$ boundary triggered `ATTRIBUTE_GAP`.
2. **Deterministic Transparency**: Rather than artificially manipulating thresholds to report 100%, CatalogIQ preserves deterministic mathematical boundaries ($N_{relevant} < 4$, $\text{Coverage} < 0.60$).

---

## 8. Product Decisions & Tradeoffs

1. **Why Deterministic Scoring instead of an End-to-End ML Model?**
   E-commerce catalog operations require 100% auditability and explainability. A product manager or vendor manager needs to know *precisely why* an item received a health score of 62 (e.g., missing `fit` and `material`) rather than debugging a black-box neural regression weight.
2. **Why Keyword/Attribute Matching instead of Vector Embeddings?**
   Vector embeddings often hallucinate semantic relevance across incompatible attributes (e.g. matching an oversized women's shirt to a men's regular kurta). Deterministic attribute matching enforces exact catalog schema taxonomy, guaranteeing predictable discovery diagnostics.
3. **Why is the LLM Used Only for Explanation, Never for Scoring or Decisions?**
   Decisions affecting product priority and vendor action items must be reproducible and deterministic. LLMs excel at summarizing structured data into plain-language executive takeaways, but should never be in the critical path of arithmetic calculations, scoring, or root cause logic.
4. **Why Synthetic Data?**
   Allows controlled, reproducible defect injection (e.g. specific missing attributes on black kurtas) without exposing proprietary enterprise customer traffic or catalog data.

---

## 9. Limitations

> **Explicit Notice**: This prototype uses synthetic/demo fashion catalog and search data. It does not use private Myntra data or claim to represent Myntra's production systems. Business impact figures are modeled estimates, not observed production metrics.

---

## 10. How to Run Locally

### 1. Setup Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Seed Database & CSV Files (seed=42)
```bash
python -m backend.seed_data
```

### 3. Start Backend Server
```bash
uvicorn backend.main:app --reload --port 8000
```
- **API Documentation (Swagger UI)**: `http://localhost:8000/docs`
- **Health / Dashboard Endpoint**: `http://localhost:8000/api/dashboard`

### 4. Run Evaluation & Tests
```bash
# Run ground-truth evaluation
python -m backend.evaluate

# Run unit and API tests
pytest backend/tests/test_core_logic.py -v
```

---

## 11. API Reference

### `GET /api/dashboard`
Returns catalog health distribution, search volume, average CTR/CVR, root cause breakdown, and top 5 priority opportunities.

### `GET /api/products`
Lists catalog products with pagination and filters (`category`, `gender`, `health_classification`, `q`, `page`, `page_size`).

### `GET /api/products/{product_id}`
Returns product health breakdown, missing attributes list, and remediation advice.

### `GET /api/searches`
Lists search queries with filters (`root_cause`, `min_opportunity_score`, `sort_by`, `order`).

### `GET /api/searches/{query_id}`
Returns deep-dive query diagnostics, coverage ratio, 4 opportunity sub-scores, and `missing_attributes_breakdown`.

### `GET /api/opportunities`
Returns prioritized list of actionable search opportunities sorted descending by `Opportunity Score`.

### `POST /api/explain`
Generates plain-language executive explanations and recommended actions.
- **Request Body**: `{"query_id": "Q001"}` or raw `{"query_data": {...}}`.
- **Response**:
```json
{
  "query_id": "Q001",
  "query": "black oversized kurta men",
  "root_cause": "ATTRIBUTE_GAP",
  "opportunity_score": 84.5,
  "explanation": "The search query 'black oversized kurta men' generates 8,420 monthly impressions with a low CTR of 2.2% and conversion rate of 20.54%. While relevant inventory exists, discovery coverage is restricted to 0.0% because 18 catalog products are missing fit tags. This represents an opportunity score of 84.5/100, and enriching these metadata attributes will immediately restore search discoverability.",
  "source": "template_fallback",
  "model": "rule-based-template"
}
```
*(If `OPENAI_API_KEY` is configured in `.env`, the endpoint calls the live LLM; otherwise it falls back seamlessly to the deterministic template without crashing).*
