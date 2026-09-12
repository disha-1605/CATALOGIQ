"""Search performance analysis, catalog coverage calculation, and root cause diagnosis."""

from typing import Dict, Any, List, Tuple
from backend.catalog_analyzer import extract_query_intent, evaluate_product_match

# Explicit Threshold Constants for Root Cause Engine
INVENTORY_THRESHOLD = 4        # Minimum relevant items in catalog to avoid INVENTORY_GAP
COVERAGE_THRESHOLD = 0.60      # Minimum coverage ratio (correct/relevant) to avoid ATTRIBUTE_GAP


def calculate_search_metrics(impressions: int, clicks: int, orders: int) -> Tuple[float, float]:
    """
    Calculate Click-Through Rate (CTR) and Conversion Rate (CVR).
    Ensures mathematical integrity.
    """
    if impressions <= 0:
        return 0.0, 0.0
        
    ctr = clicks / impressions
    cvr = (orders / clicks) if clicks > 0 else 0.0
    
    return round(ctr, 4), round(cvr, 4)


def analyze_query_coverage(
    query_str: str,
    products: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Perform deterministic matching across the entire catalog for a search query.
    Calculates coverage, missing attributes breakdown, and affected products.
    """
    intent = extract_query_intent(query_str)
    
    relevant_products: List[Dict[str, Any]] = []
    correctly_matching_products: List[Dict[str, Any]] = []
    missing_attrs_counter: Dict[str, int] = {}
    
    for prod in products:
        is_rel, is_correct, details = evaluate_product_match(prod, intent)
        if is_rel:
            relevant_products.append(prod)
            if is_correct:
                correctly_matching_products.append(prod)
            else:
                for missing_attr in details["missing_attributes"]:
                    missing_attrs_counter[missing_attr] = missing_attrs_counter.get(missing_attr, 0) + 1

    total_relevant = len(relevant_products)
    total_correct = len(correctly_matching_products)
    
    if total_relevant > 0:
        coverage = total_correct / total_relevant
    else:
        coverage = 0.0
        
    coverage = round(coverage, 4)
    
    # Diagnose Root Cause
    if total_relevant < INVENTORY_THRESHOLD:
        root_cause = "INVENTORY_GAP"
        affected_count = 0  # Missing products in inventory rather than existing defective products
        missing_attrs_breakdown = {}
    elif coverage < COVERAGE_THRESHOLD:
        root_cause = "ATTRIBUTE_GAP"
        affected_count = total_relevant - total_correct
        missing_attrs_breakdown = missing_attrs_counter
    else:
        root_cause = "NO_CATALOG_GAP_DETECTED"
        affected_count = 0
        missing_attrs_breakdown = {}
        
    return {
        "intent": intent,
        "total_relevant": total_relevant,
        "total_correct": total_correct,
        "catalog_coverage": coverage,
        "root_cause": root_cause,
        "affected_products_count": affected_count,
        "missing_attributes_breakdown": missing_attrs_breakdown,
        "relevant_products": relevant_products,
        "correctly_matching_products": correctly_matching_products,
    }
