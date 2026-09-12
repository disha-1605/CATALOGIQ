"""Deterministic Fashion Query Intent Extractor and Product Matching Engine."""

import re
from typing import Dict, Any, List, Optional, Set, Tuple

# Controlled Fashion Vocabulary Mapping
VOCABULARY_GENDERS = {
    "men": "Men",
    "mens": "Men",
    "man": "Men",
    "male": "Men",
    "women": "Women",
    "womens": "Women",
    "woman": "Women",
    "female": "Women",
    "unisex": "Unisex",
    "girls": "Women",
    "boys": "Men",
}

VOCABULARY_CATEGORIES = {
    "kurta": "Kurtas",
    "kurtas": "Kurtas",
    "kurti": "Kurtas",
    "anarkali": "Kurtas",
    "shirt": "Shirts",
    "shirts": "Shirts",
    "jeans": "Jeans",
    "jean": "Jeans",
    "dress": "Dresses",
    "dresses": "Dresses",
    "gown": "Dresses",
    "maxi": "Dresses",
    "sneaker": "Sneakers",
    "sneakers": "Sneakers",
    "running shoes": "Running Shoes",
    "running shoe": "Running Shoes",
    "sports shoes": "Running Shoes",
    "jacket": "Jackets",
    "jackets": "Jackets",
    "blazer": "Jackets",
    "bomber": "Jackets",
    "t-shirt": "T-shirts",
    "tshirt": "T-shirts",
    "t-shirts": "T-shirts",
    "tshirts": "T-shirts",
    "tee": "T-shirts",
    "tees": "T-shirts",
    "trouser": "Trousers",
    "trousers": "Trousers",
    "pants": "Trousers",
    "cargo": "Trousers",
    "cargos": "Trousers",
    "cargo pants": "Trousers",
    "handbag": "Handbags",
    "handbags": "Handbags",
    "bag": "Handbags",
    "bags": "Handbags",
    "tote": "Handbags",
}

VOCABULARY_COLORS = {
    "black", "white", "blue", "navy", "red", "green", "yellow", 
    "pink", "beige", "grey", "gray", "brown", "maroon", "olive"
}

VOCABULARY_FITS = {
    "oversized", "slim", "regular", "relaxed", "skinny", "wide leg", "loose", "straight"
}

VOCABULARY_MATERIALS = {
    "cotton", "linen", "denim", "leather", "silk", "polyester", "viscose", "wool", "waterproof"
}

VOCABULARY_PATTERNS = {
    "solid", "printed", "striped", "floral", "checked", "embroidered"
}

VOCABULARY_SLEEVES = {
    "full sleeve", "half sleeve", "sleeveless", "long sleeve", "short sleeve"
}


def extract_query_intent(query_str: str) -> Dict[str, Any]:
    """
    Deterministically extract structured fashion attributes from raw search query.
    
    Example:
    'black oversized kurta men' -> {
        'gender': 'Men',
        'category': 'Kurtas',
        'color': 'black',
        'fit': 'oversized',
        'material': None,
        'pattern': None,
        'sleeve': None,
        'raw_tokens': ['black', 'oversized', 'kurta', 'men']
    }
    """
    cleaned_query = query_str.lower().strip()
    # Normalize punctuation
    normalized = re.sub(r"[^\w\s-]", " ", cleaned_query)
    
    intent: Dict[str, Any] = {
        "gender": None,
        "category": None,
        "color": None,
        "fit": None,
        "material": None,
        "pattern": None,
        "sleeve": None,
        "raw_tokens": [t for t in normalized.split() if t],
    }
    
    # 1. Multi-word phrases first
    # Sleeves (e.g. 'full sleeve', 'half sleeve')
    for sleeve_kw in VOCABULARY_SLEEVES:
        if sleeve_kw in normalized:
            intent["sleeve"] = sleeve_kw
            normalized = normalized.replace(sleeve_kw, " ")
            
    # Fits (e.g. 'wide leg')
    if "wide leg" in normalized:
        intent["fit"] = "wide leg"
        normalized = normalized.replace("wide leg", " ")
        
    # Categories (e.g. 'running shoes', 'cargo pants')
    for multi_cat in ["running shoes", "running shoe", "sports shoes", "cargo pants"]:
        if multi_cat in normalized:
            intent["category"] = VOCABULARY_CATEGORIES[multi_cat]
            normalized = normalized.replace(multi_cat, " ")
            break

    tokens = normalized.split()
    
    # 2. Single token mapping
    for token in tokens:
        if token in VOCABULARY_GENDERS and not intent["gender"]:
            intent["gender"] = VOCABULARY_GENDERS[token]
        elif token in VOCABULARY_CATEGORIES and not intent["category"]:
            intent["category"] = VOCABULARY_CATEGORIES[token]
        elif token in VOCABULARY_COLORS and not intent["color"]:
            intent["color"] = token
        elif token in VOCABULARY_FITS and not intent["fit"]:
            intent["fit"] = token
        elif token in VOCABULARY_MATERIALS and not intent["material"]:
            intent["material"] = token
        elif token in VOCABULARY_PATTERNS and not intent["pattern"]:
            intent["pattern"] = token

    return intent


def evaluate_product_match(
    product_dict: Dict[str, Any],
    intent: Dict[str, Any]
) -> Tuple[bool, bool, Dict[str, Any]]:
    """
    Evaluate if a product matches a query intent.
    
    Returns:
    - is_relevant (bool): Belongs to the core target domain (category + gender).
    - is_correctly_matching (bool): Is relevant AND satisfies all specified modifier attributes (color, fit, material, sleeve, pattern).
    - match_details (dict): Explains matching status for each attribute.
    """
    details: Dict[str, Any] = {
        "category_match": False,
        "gender_match": False,
        "modifier_matches": {},
        "missing_attributes": [],
    }
    
    prod_cat = str(product_dict.get("category", "")).strip()
    prod_gender = str(product_dict.get("gender", "")).strip()
    prod_title = str(product_dict.get("title", "")).lower()
    prod_desc = str(product_dict.get("description", "")).lower()
    
    # 1. Category Matching
    target_cat = intent.get("category")
    if target_cat:
        if prod_cat.lower() == target_cat.lower():
            details["category_match"] = True
        elif target_cat == "Trousers" and str(product_dict.get("subcategory", "")).lower() in ["cargos", "cargo"]:
            details["category_match"] = True
    else:
        # If no explicit category in query, match all
        details["category_match"] = True

    # 2. Gender Matching
    target_gender = intent.get("gender")
    if target_gender:
        if prod_gender.lower() == target_gender.lower() or prod_gender.lower() == "unisex":
            details["gender_match"] = True
    else:
        details["gender_match"] = True

    is_relevant = details["category_match"] and details["gender_match"]
    if not is_relevant:
        return False, False, details

    # 3. Specific Modifier Matching
    # (Only checked if relevant)
    all_modifiers_matched = True
    
    # Color check
    target_color = intent.get("color")
    if target_color:
        prod_color = str(product_dict.get("color", "") or "").lower().strip()
        if prod_color == target_color or target_color in prod_title:
            details["modifier_matches"]["color"] = "matched"
        else:
            details["modifier_matches"]["color"] = "missing_or_mismatch"
            all_modifiers_matched = False
            details["missing_attributes"].append("color")

    # Fit check
    target_fit = intent.get("fit")
    if target_fit:
        prod_fit = str(product_dict.get("fit", "") or "").lower().strip()
        if prod_fit == target_fit or target_fit in prod_title:
            details["modifier_matches"]["fit"] = "matched"
        else:
            details["modifier_matches"]["fit"] = "missing_or_mismatch"
            all_modifiers_matched = False
            details["missing_attributes"].append("fit")

    # Material check
    target_material = intent.get("material")
    if target_material:
        prod_material = str(product_dict.get("material", "") or "").lower().strip()
        if prod_material == target_material or target_material in prod_title or target_material in prod_desc:
            details["modifier_matches"]["material"] = "matched"
        else:
            details["modifier_matches"]["material"] = "missing_or_mismatch"
            all_modifiers_matched = False
            details["missing_attributes"].append("material")

    # Pattern check
    target_pattern = intent.get("pattern")
    if target_pattern:
        prod_pattern = str(product_dict.get("pattern", "") or "").lower().strip()
        if prod_pattern == target_pattern or target_pattern in prod_title:
            details["modifier_matches"]["pattern"] = "matched"
        else:
            details["modifier_matches"]["pattern"] = "missing_or_mismatch"
            all_modifiers_matched = False
            details["missing_attributes"].append("pattern")

    # Sleeve check
    target_sleeve = intent.get("sleeve")
    if target_sleeve:
        prod_sleeve = str(product_dict.get("sleeve", "") or "").lower().strip()
        if prod_sleeve == target_sleeve or target_sleeve in prod_title:
            details["modifier_matches"]["sleeve"] = "matched"
        else:
            details["modifier_matches"]["sleeve"] = "missing_or_mismatch"
            all_modifiers_matched = False
            details["missing_attributes"].append("sleeve")

    is_correctly_matching = is_relevant and all_modifiers_matched
    return is_relevant, is_correctly_matching, details
