"""Dataset loader and seeder for CatalogIQ.

Loads the 200 products from products.csv and 40 search queries from searches.csv,
computes deterministic product health scores, query coverage, root cause classifications,
and opportunity scores from actual catalog data, and populates the SQLite database.
"""

import os
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any

from backend.database import SessionLocal, init_db
from backend.models import Product, SearchQuery
from backend.scoring import evaluate_product_health
from backend.search_analyzer import calculate_search_metrics, analyze_query_coverage
from backend.opportunity import calculate_opportunity_scores

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_products_from_csv(csv_path: str = None) -> List[Dict[str, Any]]:
    """Load and score 200 products from products.csv."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "products.csv")
        
    df = pd.read_csv(csv_path)
    df = df.replace({np.nan: None})
    records = df.to_dict(orient="records")
    
    scored_products = []
    for row in records:
        # Standardize price field
        price_val = float(row.get("price_inr") or row.get("price") or 0.0)
        prod_dict = {
            "product_id": str(row["product_id"]),
            "brand": str(row["brand"]),
            "title": str(row["title"]),
            "description": str(row["description"]),
            "category": str(row["category"]),
            "subcategory": str(row.get("subcategory") or row["category"].lower()),
            "gender": str(row["gender"]),
            "color": row.get("color"),
            "material": row.get("material"),
            "fit": row.get("fit"),
            "sleeve": row.get("sleeve"),
            "pattern": row.get("pattern"),
            "price": price_val,
            "image_url": str(row.get("image_url") or f"assets/products/{row['category'].lower()}/placeholder.webp"),
            "injected_defect": str(row.get("injected_defect") or "none"),
        }
        
        # Calculate deterministic health scores
        health_eval = evaluate_product_health(prod_dict)
        prod_dict.update({
            "health_score": health_eval["health_score"],
            "health_classification": health_eval["health_classification"],
            "attribute_completeness_score": health_eval["attribute_completeness"],
            "title_quality_score": health_eval["title_quality"],
            "description_quality_score": health_eval["description_quality"],
            "category_consistency_score": health_eval["category_consistency"],
            "missing_attributes": json.dumps(health_eval["missing_attributes"]),
            "quality_issues": json.dumps(health_eval["quality_issues"]),
        })
        scored_products.append(prod_dict)
        
    return scored_products


def load_searches_from_csv(products: List[Dict[str, Any]], csv_path: str = None) -> List[Dict[str, Any]]:
    """Load and analyze 40 search queries from searches.csv."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "searches.csv")
        
    df = pd.read_csv(csv_path)
    records = df.to_dict(orient="records")
    
    temp_searches = []
    for row in records:
        query_text = str(row["query"]).strip()
        impressions = int(row.get("impressions_monthly") or row.get("impressions") or 0)
        clicks = int(row.get("clicks_monthly") or row.get("clicks") or 0)
        orders = int(row.get("orders_monthly") or row.get("orders") or 0)
        
        ctr, cvr = calculate_search_metrics(impressions, clicks, orders)
        
        # Calculate coverage and root cause from actual product catalog
        coverage_result = analyze_query_coverage(query_text, products)
        
        search_item = {
            "query_id": str(row["query_id"]),
            "query": query_text,
            "impressions": impressions,
            "clicks": clicks,
            "orders": orders,
            "ctr": ctr,
            "conversion_rate": cvr,
            "extracted_intent": json.dumps(coverage_result["intent"]),
            "relevant_products_count": coverage_result["total_relevant"],
            "correctly_matching_count": coverage_result["total_correct"],
            "catalog_coverage": coverage_result["catalog_coverage"],
            "root_cause": coverage_result["root_cause"],
            "affected_products_count": coverage_result["affected_products_count"],
            "missing_attributes_breakdown": json.dumps(coverage_result["missing_attributes_breakdown"]),
        }
        temp_searches.append(search_item)
        
    min_vol = min(s["impressions"] for s in temp_searches) if temp_searches else 1
    max_vol = max(s["impressions"] for s in temp_searches) if temp_searches else 10000
    
    searches = []
    for s in temp_searches:
        opp_scores = calculate_opportunity_scores(
            s, min_volume=min_vol, max_volume=max_vol
        )
        s.update({
            "opportunity_score": opp_scores["opportunity_score"],
            "demand_score": opp_scores["demand_score"],
            "friction_score": opp_scores["friction_score"],
            "gap_score": opp_scores["gap_score"],
            "fixability_score": opp_scores["fixability_score"],
            "recommended_action": opp_scores["recommended_action"],
        })
        searches.append(s)
        
    return searches


def generate_synthetic_products(count: int = 200) -> List[Dict[str, Any]]:
    """Compatibility wrapper for tests: loads products from dataset."""
    return load_products_from_csv()


def generate_synthetic_searches(products: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Compatibility wrapper for tests: loads searches from dataset."""
    if products is None:
        products = load_products_from_csv()
    return load_searches_from_csv(products)


def seed_database_and_csvs():
    """Load dataset from CSVs, calculate all metrics, and seed SQLite database."""
    print("Loading and scoring 200 catalog products...")
    products = load_products_from_csv()
    
    print("Loading and diagnosing 40 search queries against catalog...")
    searches = load_searches_from_csv(products)
    
    print("Populating SQLite database (catalogiq.db)...")
    init_db()
    db = SessionLocal()
    try:
        db.query(Product).delete()
        db.query(SearchQuery).delete()
        db.commit()
        
        for p in products:
            prod_record = Product(
                product_id=p["product_id"],
                brand=p["brand"],
                title=p["title"],
                description=p["description"],
                category=p["category"],
                subcategory=p["subcategory"],
                gender=p["gender"],
                color=p["color"],
                material=p["material"],
                fit=p["fit"],
                sleeve=p["sleeve"],
                pattern=p["pattern"],
                price=p["price"],
                image_url=p["image_url"],
                injected_defect=p["injected_defect"],
                health_score=p["health_score"],
                health_classification=p["health_classification"],
                attribute_completeness_score=p["attribute_completeness_score"],
                title_quality_score=p["title_quality_score"],
                description_quality_score=p["description_quality_score"],
                category_consistency_score=p["category_consistency_score"],
                missing_attributes=p["missing_attributes"],
                quality_issues=p["quality_issues"],
            )
            db.add(prod_record)
            
        for s in searches:
            search_record = SearchQuery(
                query_id=s["query_id"],
                query=s["query"],
                impressions=s["impressions"],
                clicks=s["clicks"],
                orders=s["orders"],
                ctr=s["ctr"],
                conversion_rate=s["conversion_rate"],
                extracted_intent=s["extracted_intent"],
                relevant_products_count=s["relevant_products_count"],
                correctly_matching_count=s["correctly_matching_count"],
                catalog_coverage=s["catalog_coverage"],
                root_cause=s["root_cause"],
                affected_products_count=s["affected_products_count"],
                missing_attributes_breakdown=s["missing_attributes_breakdown"],
                opportunity_score=s["opportunity_score"],
                demand_score=s["demand_score"],
                friction_score=s["friction_score"],
                gap_score=s["gap_score"],
                fixability_score=s["fixability_score"],
                recommended_action=s["recommended_action"],
            )
            db.add(search_record)
            
        db.commit()
        print(f"Successfully seeded database with {len(products)} products and {len(searches)} search queries.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database_and_csvs()
