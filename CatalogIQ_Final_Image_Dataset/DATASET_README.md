# CatalogIQ Final Image Dataset

## Overview
The CatalogIQ Final Image Dataset is a self-contained, enterprise-grade fashion e-commerce benchmark dataset designed for hackathon evaluation, catalog health diagnosis, search intelligence analysis, and root cause opportunity scoring.

## Visual Fidelity & Image Strategy
All 200 product images (`P001.jpg` through `P200.jpg`) represent photorealistic, studio-quality e-commerce product photography generated deterministically from each SKU's complete metadata specification:
- **Category & Garment Silhouette**: 100% visual consistency with the defined category (Jacket, Cargo Pants, Kurta, Shirt, Trousers, Dress, Sneakers, Running Shoes, Handbag, Jeans, T-Shirt).
- **Color & Fabric Profile**: True-to-life color grading matching dominant colorways (`black`, `beige`, `grey`, `olive`, `white`, `blue`, `red`, `pink`, `navy`, `green`, `brown`).
- **Studio E-Commerce Quality**: Clean neutral studio backgrounds, centered product framing, high resolution, no illustrations, no cartoons, no vector graphics, and no unrelated people or lifestyle distractions.

## Contents
- `products.csv`: 200 synthetic fashion SKUs with comprehensive metadata (brand, title, category, gender, color, material, fit, sleeve, pattern, price_inr, relative image path, and injected catalog defect annotations).
- `searches.csv`: 40 high-intent search queries with monthly impressions, clicks, orders, CTR, and CVR.
- `root_cause_ground_truth.csv`: Benchmark ground-truth classifications (Attribute Gap vs Inventory Gap).
- `image_manifest.csv`: Complete metadata manifest mapping each product SKU to its local asset path, source classification, and visual validation status.
- `visual_validation_report.csv`: Itemized visual verification review confirming attribute match for all 200 products.
- `contact_sheet_200.jpg`: Complete visual contact sheet displaying all 200 products with labeled SKU IDs for rapid visual inspection.
- `images/`: 200 high-resolution, photorealistic, studio e-commerce product photographs (`P001.jpg` to `P200.jpg`).

## Synthetic Data Disclosure
All SKU descriptions, performance metrics, and search signals are synthetically generated for benchmark evaluation. All prices are specified in Indian Rupees (INR ₹).
