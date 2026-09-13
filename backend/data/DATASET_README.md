# CatalogIQ Final Demo Dataset

This dataset is designed for the CatalogIQ MVP: Search → Catalog → Root Cause → Opportunity.

## Files
- `products.csv` — 200 synthetic fashion SKUs with controlled catalog defects and category-specific image paths.
- `searches.csv` — 40 synthetic monthly search queries with impressions, clicks and orders.
- `root_cause_ground_truth.csv` — controlled labels for evaluating the rule-based root-cause engine.

## Product images
Each SKU has an `image_url` such as:
`assets/products/kurta/kurta-01.webp`

The important design requirement is that image assignment is category-specific and uses multiple image IDs. The frontend should render `image_url` rather than hard-code one image.

Create 8–12 visually appropriate images per major category (kurta, shirt, jeans, sneakers, etc.) and map them to these paths. Reuse within a category is acceptable; do not reuse a kurta image for shirts, jeans or shoes.

## Data integrity
- CTR = clicks / impressions
- Conversion rate = orders / clicks
- Search metrics are therefore internally consistent.
- Root-cause labels are controlled ground truth for the evaluation set.
- Catalog Health, query matching, coverage and Opportunity Score should be calculated by the application, not stored as fake final scores in the UI.

## Synthetic-data disclosure
This is synthetic/demo data created to demonstrate product reasoning and system behavior. It does not represent private Myntra data or Myntra's production systems.
