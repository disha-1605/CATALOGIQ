"""Deterministic synthetic dataset generator for CatalogIQ (seed=42).

Generates 200 realistic Indian fashion products across 10 categories with controlled defects
and 40 realistic search queries with traffic metrics, root causes, and opportunity scores.
"""

import os
import json
import random
import pandas as pd
from typing import List, Dict, Any

from backend.database import SessionLocal, init_db
from backend.models import Product, SearchQuery
from backend.scoring import evaluate_product_health
from backend.search_analyzer import calculate_search_metrics, analyze_query_coverage
from backend.opportunity import calculate_opportunity_scores

RANDOM_SEED = 42

# Realistic Indian E-commerce Brands
BRANDS = {
    "Kurtas": ["FabIndia", "Manyavar", "Anouk", "Libas", "W", "House of Pataudi", "Taavi", "Soch"],
    "Shirts": ["Roadster", "Allen Solly", "Wrogn", "Peter England", "Louis Philippe", "Highlander"],
    "Jeans": ["Levi's", "Flying Machine", "Spykar", "Roadster", "Jack & Jones", "Pepe Jeans"],
    "Dresses": ["DressBerry", "Tokyo Talkies", "Biba", "Forever 21", "AND", "MANGO"],
    "Sneakers": ["Puma", "Nike", "Adidas", "HRX", "Red Tape", "Campus"],
    "Running Shoes": ["Nike", "Asics", "Puma", "Adidas", "Reebok", "Decathlon Kalenji"],
    "Jackets": ["Roadster", "HRX", "Wildcraft", "Fort Collins", "Monte Carlo", "Puma"],
    "T-shirts": ["HRX", "Roadster", "Puma", "Bewakoof", "Wrogn", "Jack & Jones", "Souled Store"],
    "Trousers": ["Allen Solly", "Peter England", "Blackberrys", "Highlander", "Mark & Spencer"],
    "Handbags": ["Lavie", "Baggit", "Caprese", "Lino Perros", "Hidesign", "Accessorize London"],
}

COLORS = ["Black", "White", "Blue", "Navy", "Red", "Green", "Yellow", "Pink", "Beige", "Grey", "Brown", "Maroon", "Olive"]
MATERIALS = {
    "Kurtas": ["Cotton", "Silk", "Linen", "Viscose", "Rayon"],
    "Shirts": ["Cotton", "Linen", "Polyester", "Denim"],
    "Jeans": ["Denim", "Cotton"],
    "Dresses": ["Cotton", "Silk", "Polyester", "Viscose", "Rayon"],
    "Sneakers": ["Canvas", "Leather", "Mesh", "Synthetic"],
    "Running Shoes": ["Mesh", "Synthetic", "Waterproof", "Knit"],
    "Jackets": ["Leather", "Polyester", "Denim", "Nylon"],
    "T-shirts": ["Cotton", "Polyester", "Viscose"],
    "Trousers": ["Cotton", "Linen", "Polyester", "Viscose"],
    "Handbags": ["Leather", "Synthetic", "Canvas", "Jute"],
}
FITS = ["Regular", "Slim", "Oversized", "Relaxed", "Skinny", "Wide Leg", "Straight"]
SLEEVES = ["Full Sleeve", "Half Sleeve", "Sleeveless", "Short Sleeve", "Long Sleeve"]
PATTERNS = ["Solid", "Printed", "Striped", "Floral", "Checked", "Embroidered"]


def generate_synthetic_products(count: int = 200) -> List[Dict[str, Any]]:
    """
    Generate ~200 fashion products across 10 categories with controlled catalog defects.
    """
    random.seed(RANDOM_SEED)
    categories = [
        "Kurtas", "Shirts", "Jeans", "Dresses", "Sneakers", 
        "Running Shoes", "Jackets", "T-shirts", "Trousers", "Handbags"
    ]
    
    products = []
    items_per_category = count // len(categories)
    
    prod_idx = 1
    for cat in categories:
        for i in range(items_per_category):
            brand = random.choice(BRANDS[cat])
            color = random.choice(COLORS)
            material = random.choice(MATERIALS[cat])
            fit = random.choice(FITS) if cat not in ["Sneakers", "Running Shoes", "Handbags"] else None
            sleeve = random.choice(SLEEVES) if cat in ["Kurtas", "Shirts", "Dresses", "Jackets", "T-shirts"] else None
            pattern = random.choice(PATTERNS) if cat not in ["Sneakers", "Running Shoes"] else None
            
            # Category-specific demographics & inventory modeling
            if cat == "Kurtas":
                gender = "Women" if i >= 18 else "Men"
                subcategory = "Ethnic Kurta" if gender == "Men" else "Anarkali Kurta"
                price = random.choice([799, 1299, 1599, 2199, 2999])
            elif cat == "Shirts":
                gender = "Women" if i >= 18 else "Men"
                subcategory = "Formal Shirt" if i < 12 else "Casual Shirt"
                if gender == "Men" and i < 12:
                    color = "White" if i < 8 else "Blue"
                    material = "Cotton"
                price = random.choice([899, 1199, 1499, 1999])
            elif cat == "Jeans":
                gender = "Women" if i >= 12 else "Men"
                subcategory = "Slim Fit Jeans" if gender == "Men" else "Wide Leg Jeans"
                if gender == "Men" and i < 8:
                    color = "Blue"
                    fit = "Slim"
                price = random.choice([1299, 1799, 2499, 3299])
            elif cat == "Dresses":
                gender = "Women"
                subcategory = "Maxi Dress" if i % 2 == 0 else "Midi Dress"
                if i < 8:
                    color = "Pink"
                price = random.choice([1299, 1899, 2499, 3499])
            elif cat == "Sneakers":
                if i >= 18:
                    gender = "Women"
                elif i >= 16:
                    gender = "Unisex"
                else:
                    gender = "Men"
                    if i < 10:
                        color = "White"
                subcategory = "Low-Top Sneakers"
                price = random.choice([1999, 2799, 3999, 5499])
            elif cat == "Running Shoes":
                gender = "Women" if i >= 18 else "Men"
                subcategory = "Athletic Shoes"
                if gender == "Men" and i < 12:
                    color = "Black"
                    material = "Mesh"
                price = random.choice([2499, 3499, 4999, 6999])
            elif cat == "Jackets":
                gender = "Women" if i >= 18 else "Men"
                subcategory = "Bomber Jacket" if gender == "Men" else "Biker Jacket"
                if gender == "Men" and i < 12:
                    material = "Denim"
                price = random.choice([1999, 2999, 4499, 5999])
            elif cat == "T-shirts":
                gender = "Women" if i >= 18 else "Men"
                subcategory = "Round Neck Tee"
                if gender == "Men" and i < 14:
                    material = "Cotton"
                    if i < 7:
                        color = "Black"
                price = random.choice([499, 699, 899, 1299])
            elif cat == "Trousers":
                gender = "Women" if i >= 18 else "Men"
                subcategory = "Cargos" if i in [16, 17] else "Chinos"
                if gender == "Men" and i < 10:
                    color = "Black"
                price = random.choice([1199, 1599, 2199, 2799])
            elif cat == "Handbags":
                gender = "Women"
                subcategory = "Tote Bag" if i < 12 else "Shoulder Bag"
                if i < 10:
                    material = "Leather"
                    color = "Brown"
                price = random.choice([1499, 2299, 3499, 4999])
            else:
                gender = "Unisex"
                subcategory = "General"
                price = 999
                
            # Default Rich Title & Description
            gender_label = "Men's" if gender == "Men" else ("Women's" if gender == "Women" else "Unisex")
            title = f"{brand} {gender_label} {color} {material} {pattern} {cat}"
            description = (
                f"Elevate your wardrobe with this {color.lower()} {cat.lower()} from {brand}. "
                f"Crafted from premium {material.lower()} fabric offering superior comfort and durability. "
                f"Features {pattern.lower() if pattern else 'clean'} design, suitable for casual outings and daily wear. "
                f"Wash care: Machine wash cold with similar colors."
            )
            
            # --- Controlled Catalog Defects Injection for Attribute Gaps ---
            # 1. Defect: Men's Black Kurtas missing fit attribute
            if cat == "Kurtas" and gender == "Men" and i in [0, 2, 4, 6, 8, 10]:
                color = "Black"
                fit = None  # Missing fit defect
                title = f"{brand} Men's Black Pure Cotton Kurta"
                
            # 2. Defect: Men's Oversized T-shirts missing fit
            if cat == "T-shirts" and gender == "Men" and i in [0, 2, 4, 6, 8]:
                fit = None
                
            # 3. Defect: Linen Shirts missing material / sleeve
            if cat == "Shirts" and gender == "Men" and i in [12, 13, 14, 15]:
                material = None
                sleeve = None
                
            # 4. Defect: Wide Leg Jeans missing fit
            if cat == "Jeans" and gender == "Women":
                fit = None
                
            # 5. Defect: Weak title (< 18 chars)
            if i == 1:
                title = f"{gender_label} {cat}"
                
            # 6. Defect: Short description (< 30 chars)
            if i == 2:
                description = f"Nice {cat.lower()} for daily wear."

            prod_id = f"PROD_{prod_idx:03d}"
            prod_dict = {
                "product_id": prod_id,
                "brand": brand,
                "title": title,
                "description": description,
                "category": cat,
                "subcategory": subcategory,
                "gender": gender,
                "color": color,
                "material": material,
                "fit": fit,
                "sleeve": sleeve,
                "pattern": pattern,
                "price": float(price),
            }
            
            # Evaluate health score & classification
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
            
            products.append(prod_dict)
            prod_idx += 1
            
    return products


def generate_synthetic_searches(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate 40 realistic search queries with mathematically connected traffic metrics,
    root causes, and opportunity scores.
    """
    random.seed(RANDOM_SEED)
    
    query_templates = [
        # --- Group A: High Demand + ATTRIBUTE_GAP (Adequate Catalog Depth >= 4, Low Coverage < 60%) ---
        ("black oversized kurta men", 8420, 185, 38),
        ("oversized t shirt men", 9200, 210, 42),
        ("linen shirt men", 7600, 190, 45),
        ("wide leg jeans women", 8100, 195, 41),
        ("relaxed cargo pants", 6800, 160, 32),
        ("grey oversized hoodie men", 5200, 110, 22),
        ("sleeveless summer dress women", 4800, 95, 18),
        ("striped cotton shirt men", 4900, 105, 20),
        ("olive green cargo pants", 4600, 90, 16),
        ("black casual trousers men", 4500, 95, 18),
        ("slim fit jeans men", 7400, 180, 40),
        ("floral maxi dress women", 6500, 150, 31),
        ("navy blue formal trousers men", 4100, 85, 15),
        ("printed anarkali kurta women", 5100, 115, 24),

        # --- Group B: High Demand + INVENTORY_GAP (Catalog Depth < 4 Items) ---
        ("waterproof running shoes women", 6200, 75, 12),
        ("white silk ethnic jacket women", 5400, 60, 8),
        ("green running shoes women", 4300, 50, 8),
        ("maroon embroidered kurta women", 5700, 70, 11),
        ("black sneakers women", 8300, 110, 18),
        ("yellow linen trousers women", 3900, 45, 7),
        ("silk anarkali kurta women", 5800, 68, 12),
        ("red leather jacket women", 5100, 62, 10),
        ("women formal trousers", 4400, 55, 9),
        ("women bomber jacket", 4700, 60, 10),
        ("white athletic running shoes women", 4200, 48, 7),
        ("women leather sneakers", 4900, 58, 9),
        ("women casual shirts", 4600, 52, 8),

        # --- Group C: Healthy Discovery (NO_CATALOG_GAP_DETECTED: Depth >= 4, Coverage >= 60%) ---
        ("formal white shirt men", 7100, 490, 168),
        ("casual blue shirt men", 6800, 440, 142),
        ("cotton t-shirt men", 6200, 390, 125),
        ("black running shoes men", 5900, 370, 118),
        ("blue slim jeans men", 5600, 350, 112),
        ("casual denim jacket men", 5200, 320, 98),
        ("women tote handbag", 4900, 300, 92),
        ("women pink dress", 4700, 280, 86),
        ("white sneakers men", 6400, 410, 134),
        ("solid black t shirt men", 4200, 260, 80),
        ("brown leather handbag women", 3600, 220, 68),
        ("leather handbag women", 6900, 420, 138),
        ("cotton summer dress women", 7900, 460, 152),
    ]
    
    # First pass: compute traffic and coverage
    temp_searches = []
    for idx, (query_text, impressions, clicks, orders) in enumerate(query_templates, start=1):
        ctr, cvr = calculate_search_metrics(impressions, clicks, orders)
        coverage_result = analyze_query_coverage(query_text, products)
        
        item = {
            "query_id": f"Q{idx:03d}",
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
            "intent": coverage_result["intent"],
        }
        temp_searches.append(item)

    # Compute Opportunity Scores based on global distribution
    min_vol = min(s["impressions"] for s in temp_searches)
    max_vol = max(s["impressions"] for s in temp_searches)
    
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


def seed_database_and_csvs():
    """
    Generate datasets, save to CSV files, and seed SQLite database.
    """
    print("Generating synthetic product catalog (~200 items)...")
    products = generate_synthetic_products(200)
    
    print("Generating search query dataset (~40 queries)...")
    searches = generate_synthetic_searches(products)
    
    # Save CSVs
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    
    prod_df = pd.DataFrame(products)
    prod_csv_path = os.path.join(data_dir, "products.csv")
    prod_df.to_csv(prod_csv_path, index=False)
    print(f"Saved products CSV to: {prod_csv_path} ({len(prod_df)} records)")
    
    search_df = pd.DataFrame(searches)
    # Drop temp internal key before CSV export
    search_csv_df = search_df.drop(columns=["intent"]) if "intent" in search_df.columns else search_df
    search_csv_path = os.path.join(data_dir, "searches.csv")
    search_csv_df.to_csv(search_csv_path, index=False)
    print(f"Saved searches CSV to: {search_csv_path} ({len(search_csv_df)} records)")
    
    # Seed Database
    print("Initializing and populating SQLite database...")
    init_db()
    db = SessionLocal()
    try:
        # Clear existing
        db.query(Product).delete()
        db.query(SearchQuery).delete()
        db.commit()
        
        # Insert Products
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
            
        # Insert Searches
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
