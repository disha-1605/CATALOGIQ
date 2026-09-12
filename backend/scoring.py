"""Catalog Health Score calculation engine for CatalogIQ.

Deterministic, explainable scoring based on:
1. Attribute Completeness (40%)
2. Title Quality (25%)
3. Description Quality (20%)
4. Category Consistency (15%)
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass


@dataclass
class ScoringWeights:
    """Configurable weights for product health scoring."""
    attribute_completeness: float = 0.40
    title_quality: float = 0.25
    description_quality: float = 0.20
    category_consistency: float = 0.15

    def validate(self):
        total = self.attribute_completeness + self.title_quality + self.description_quality + self.category_consistency
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


DEFAULT_WEIGHTS = ScoringWeights()

# Category-specific expected attributes
CORE_ATTRIBUTES = ["brand", "title", "description", "category", "subcategory", "gender", "color", "material", "price"]
APPAREL_CATEGORIES = {"Kurtas", "Shirts", "Jeans", "Dresses", "T-shirts", "Trousers", "Jackets"}
UPPER_APPAREL_CATEGORIES = {"Kurtas", "Shirts", "Dresses", "T-shirts", "Jackets"}
FOOTWEAR_CATEGORIES = {"Sneakers", "Running Shoes"}
ACCESSORY_CATEGORIES = {"Handbags"}

# Category keyword map for consistency verification
CATEGORY_KEYWORDS = {
    "Kurtas": ["kurta", "kurti", "anarkali", "ethnic", "sherwani", "tunic"],
    "Shirts": ["shirt", "button-down", "oxford", "formal shirt", "casual shirt"],
    "Jeans": ["jeans", "denim", "trouser", "pants", "skinny", "wide leg"],
    "Dresses": ["dress", "gown", "maxi", "midi", "frock", "jumpsuit"],
    "Sneakers": ["sneaker", "sneakers", "trainer", "shoe", "footwear", "low-top", "high-top"],
    "Running Shoes": ["running", "sports shoe", "trainer", "athletic", "shoe", "marathon"],
    "Jackets": ["jacket", "bomber", "blazer", "coat", "windbreaker", "biker"],
    "T-shirts": ["t-shirt", "tshirt", "tee", "crewneck", "polo"],
    "Trousers": ["trouser", "trousers", "pant", "pants", "chino", "cargos", "cargo"],
    "Handbags": ["handbag", "bag", "tote", "purse", "clutch", "satchel", "shoulder bag"],
}


def get_expected_attributes(category: str) -> List[str]:
    """Return the list of expected attributes based on product category."""
    expected = list(CORE_ATTRIBUTES)
    if category in APPAREL_CATEGORIES:
        expected.append("fit")
    if category in UPPER_APPAREL_CATEGORIES:
        expected.append("sleeve")
        expected.append("pattern")
    return expected


def calculate_attribute_completeness(product_dict: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Calculate attribute completeness score (0-100) and identify missing attributes.
    """
    category = product_dict.get("category", "")
    expected = get_expected_attributes(category)
    
    missing = []
    populated_count = 0
    
    for attr in expected:
        val = product_dict.get(attr)
        if val is None or str(val).strip() == "" or str(val).strip().lower() in {"none", "null", "nan"}:
            missing.append(attr)
        else:
            populated_count += 1
            
    score = (populated_count / len(expected)) * 100.0 if expected else 100.0
    return round(score, 2), missing


def calculate_title_quality(product_dict: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Evaluate product title quality (0-100) based on length, brand/category presence,
    and descriptive specificity.
    """
    title = str(product_dict.get("title", "")).strip()
    brand = str(product_dict.get("brand", "")).strip().lower()
    category = str(product_dict.get("category", "")).strip().lower()
    gender = str(product_dict.get("gender", "")).strip().lower()
    color = str(product_dict.get("color", "") or "").strip().lower()
    
    issues = []
    points = 0.0
    
    # 1. Length check (ideal: 20-80 chars)
    title_len = len(title)
    if title_len >= 20 and title_len <= 90:
        points += 30.0
    elif 12 <= title_len < 20:
        points += 15.0
        issues.append("Title is too brief (< 20 characters)")
    elif title_len > 90:
        points += 20.0
        issues.append("Title is unusually long (> 90 characters)")
    else:
        points += 0.0
        issues.append("Title is critically short / incomplete (< 12 characters)")
        
    title_lower = title.lower()
    
    # 2. Brand presence (+20 pts)
    if brand and brand in title_lower:
        points += 20.0
    else:
        issues.append(f"Brand '{brand}' not found in title")
        
    # 3. Category / Subcategory presence (+25 pts)
    cat_keywords = CATEGORY_KEYWORDS.get(product_dict.get("category", ""), [category])
    if any(kw in title_lower for kw in cat_keywords):
        points += 25.0
    else:
        issues.append(f"Product category keyword not found in title")
        
    # 4. Gender presence (+10 pts)
    if gender and (gender in title_lower or (gender == "men" and "man" in title_lower) or (gender == "women" and "woman" in title_lower)):
        points += 10.0
        
    # 5. Key descriptive attributes (color, material, fit) (+15 pts)
    descriptive_tokens = [color, str(product_dict.get("material", "") or "").lower(), str(product_dict.get("fit", "") or "").lower()]
    found_modifiers = sum(1 for token in descriptive_tokens if token and token in title_lower)
    if found_modifiers >= 2:
        points += 15.0
    elif found_modifiers == 1:
        points += 10.0
    else:
        issues.append("Title lacks key descriptive modifiers (color, fit, or material)")
        
    return min(100.0, max(0.0, round(points, 2))), issues


def calculate_description_quality(product_dict: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Evaluate description quality (0-100) based on length, detail richness,
    material/wash care/styling guidance.
    """
    desc = str(product_dict.get("description", "")).strip()
    issues = []
    points = 0.0
    
    desc_len = len(desc)
    
    # 1. Length scoring
    if desc_len >= 120:
        points += 40.0
    elif desc_len >= 60:
        points += 25.0
    elif desc_len >= 30:
        points += 10.0
        issues.append("Description is very brief (< 60 characters)")
    else:
        points += 0.0
        issues.append("Description is missing or critically inadequate (< 30 characters)")
        
    desc_lower = desc.lower()
    
    # 2. Material / Fabric mention (+20 pts)
    material = str(product_dict.get("material", "") or "").strip().lower()
    fabric_terms = ["cotton", "linen", "silk", "denim", "leather", "polyester", "viscose", "fabric", "material", "pure"]
    if (material and material in desc_lower) or any(term in desc_lower for term in fabric_terms):
        points += 20.0
    else:
        issues.append("Description does not specify fabric / material details")
        
    # 3. Fit / Style guidance (+20 pts)
    style_terms = ["fit", "style", "wear", "occasion", "casual", "formal", "comfort", "design", "silhouette", "crafted"]
    if any(term in desc_lower for term in style_terms):
        points += 20.0
        
    # 4. Care instructions / Features (+20 pts)
    care_terms = ["wash", "care", "dry clean", "machine wash", "sole", "cushioned", "closure", "pocket", "strap", "waterproof", "durable"]
    if any(term in desc_lower for term in care_terms):
        points += 20.0
        
    return min(100.0, max(0.0, round(points, 2))), issues


def calculate_category_consistency(product_dict: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Evaluate whether product title and description are consistent with assigned category (0-100).
    Detects cross-category contamination or miscategorized items.
    """
    category = product_dict.get("category", "")
    title = str(product_dict.get("title", "")).lower()
    desc = str(product_dict.get("description", "")).lower()
    subcategory = str(product_dict.get("subcategory", "")).lower()
    
    issues = []
    score = 100.0
    
    # Check if category is recognized
    if category not in CATEGORY_KEYWORDS:
        issues.append(f"Unrecognized catalog category '{category}'")
        return 50.0, issues
        
    expected_kws = CATEGORY_KEYWORDS[category]
    combined_text = f"{title} {subcategory} {desc}"
    
    # 1. Does text contain at least one valid category keyword?
    has_valid_kw = any(kw in combined_text for kw in expected_kws)
    if not has_valid_kw:
        score -= 40.0
        issues.append(f"Product metadata lacks standard keywords for category '{category}'")
        
    # 2. Check for conflicting category keywords
    for other_cat, other_kws in CATEGORY_KEYWORDS.items():
        if other_cat == category:
            continue
        # Check if title explicitly claims to be a different incompatible category
        # e.g., Handbag in Kurtas, or Dress in T-shirts
        for kw in other_kws:
            # Match distinct word tokens to avoid substring false positives
            if f" {kw} " in f" {title} " and not any(valid_kw in title for valid_kw in expected_kws):
                score -= 40.0
                issues.append(f"Title mentions '{kw}', conflicting with assigned category '{category}'")
                break
                
    return min(100.0, max(0.0, round(score, 2))), issues


def classify_health_score(score: float) -> str:
    """
    Classify health score into four standard tiers:
    85-100 -> Excellent
    70-84  -> Good
    50-69  -> Needs Attention
    0-49   -> Critical
    """
    if score >= 85.0:
        return "Excellent"
    elif score >= 70.0:
        return "Good"
    elif score >= 50.0:
        return "Needs Attention"
    else:
        return "Critical"


def evaluate_product_health(
    product_dict: Dict[str, Any],
    weights: ScoringWeights = DEFAULT_WEIGHTS
) -> Dict[str, Any]:
    """
    Compute comprehensive Catalog Health Score and component breakdown for a product.
    """
    weights.validate()
    
    attr_score, missing_attrs = calculate_attribute_completeness(product_dict)
    title_score, title_issues = calculate_title_quality(product_dict)
    desc_score, desc_issues = calculate_description_quality(product_dict)
    cat_score, cat_issues = calculate_category_consistency(product_dict)
    
    total_score = (
        (attr_score * weights.attribute_completeness) +
        (title_score * weights.title_quality) +
        (desc_score * weights.description_quality) +
        (cat_score * weights.category_consistency)
    )
    total_score = round(total_score, 2)
    classification = classify_health_score(total_score)
    
    all_issues = title_issues + desc_issues + cat_issues
    if missing_attrs:
        all_issues.insert(0, f"Missing required attributes: {', '.join(missing_attrs)}")
        
    recommendations = []
    if missing_attrs:
        recommendations.append(f"Enrich missing attributes: {', '.join(missing_attrs)}.")
    if title_score < 70:
        recommendations.append("Update title to include Brand, Gender, Category, and primary Style/Color keywords.")
    if desc_score < 70:
        recommendations.append("Expand product description to include fabric composition, fit details, and wash care.")
    if cat_score < 80:
        recommendations.append(f"Review category classification; verify product aligns with '{product_dict.get('category')}'.")
        
    return {
        "health_score": total_score,
        "health_classification": classification,
        "attribute_completeness": attr_score,
        "title_quality": title_score,
        "description_quality": desc_score,
        "category_consistency": cat_score,
        "missing_attributes": missing_attrs,
        "quality_issues": all_issues,
        "recommendations": recommendations,
    }
