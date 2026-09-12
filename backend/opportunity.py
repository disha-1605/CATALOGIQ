"""Opportunity scoring engine and prioritized recommendation generator."""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class OpportunityWeights:
    """Configurable weights for opportunity scoring."""
    demand: float = 0.40
    friction: float = 0.30
    gap: float = 0.20
    fixability: float = 0.10

    def validate(self):
        total = self.demand + self.friction + self.gap + self.fixability
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"Opportunity weights must sum to 1.0, got {total}")


DEFAULT_OPPORTUNITY_WEIGHTS = OpportunityWeights()


def calculate_opportunity_scores(
    query_item: Dict[str, Any],
    min_volume: int,
    max_volume: int,
    min_ctr: float = 0.0,
    max_ctr: float = 0.10,
    min_cvr: float = 0.0,
    max_cvr: float = 0.50,
    weights: OpportunityWeights = DEFAULT_OPPORTUNITY_WEIGHTS
) -> Dict[str, Any]:
    """
    Compute explainable Opportunity Score (0-100) and all 4 sub-scores for a query.
    """
    weights.validate()
    
    impressions = query_item.get("impressions", query_item.get("search_volume", 0))
    ctr = query_item.get("ctr", 0.0)
    cvr = query_item.get("conversion_rate", 0.0)
    coverage = query_item.get("catalog_coverage", 0.0)
    root_cause = query_item.get("root_cause", "NO_CATALOG_GAP_DETECTED")
    
    # 1. Demand Score (0-100)
    if max_volume > min_volume:
        demand_score = ((impressions - min_volume) / (max_volume - min_volume)) * 100.0
    else:
        demand_score = 50.0
    demand_score = min(100.0, max(0.0, demand_score))
    
    # 2. Friction Score (0-100) - Higher when CTR and CVR are lower
    # Normalize CTR (0.0 to max_ctr)
    norm_ctr = min(1.0, max(0.0, (ctr - min_ctr) / (max_ctr - min_ctr))) if max_ctr > min_ctr else 0.5
    # Normalize CVR (0.0 to max_cvr)
    norm_cvr = min(1.0, max(0.0, (cvr - min_cvr) / (max_cvr - min_cvr))) if max_cvr > min_cvr else 0.5
    
    friction_score = 100.0 * (0.5 * (1.0 - norm_ctr) + 0.5 * (1.0 - norm_cvr))
    friction_score = min(100.0, max(0.0, friction_score))
    
    # 3. Catalog Gap Score (0-100) - Higher when coverage is lower
    gap_score = min(100.0, max(0.0, (1.0 - coverage) * 100.0))
    
    # 4. Fixability Score (0-100)
    if root_cause == "ATTRIBUTE_GAP":
        fixability_score = 95.0  # Catalog enrichment is fast and high ROI
    elif root_cause == "INVENTORY_GAP":
        fixability_score = 35.0  # Sourcing inventory requires lead time
    else:
        fixability_score = 10.0  # Already healthy
        
    # 1-decimal rounded sub-scores
    demand_score_rounded = round(min(100.0, max(0.0, demand_score)), 1)
    friction_score_rounded = round(min(100.0, max(0.0, friction_score)), 1)
    gap_score_rounded = round(min(100.0, max(0.0, gap_score)), 1)
    fixability_score_rounded = round(min(100.0, max(0.0, fixability_score)), 1)
        
    # Total Opportunity Score computed directly from the exact exposed component scores
    total_score = (
        (demand_score_rounded * weights.demand) +
        (friction_score_rounded * weights.friction) +
        (gap_score_rounded * weights.gap) +
        (fixability_score_rounded * weights.fixability)
    )
    total_score = round(min(100.0, max(0.0, total_score)), 1)
    
    # Recommended Action
    recommended_action = generate_recommended_action(query_item, root_cause, coverage)
    
    return {
        "demand_score": demand_score_rounded,
        "friction_score": friction_score_rounded,
        "gap_score": gap_score_rounded,
        "fixability_score": fixability_score_rounded,
        "opportunity_score": total_score,
        "recommended_action": recommended_action,
    }


def generate_recommended_action(
    query_item: Dict[str, Any],
    root_cause: str,
    coverage: float
) -> str:
    """Generate concise, actionable guidance for product and catalog managers."""
    query_text = query_item.get("query", "")
    affected = query_item.get("affected_products_count", query_item.get("affected_products", 0))
    intent = query_item.get("intent", {})
    
    if root_cause == "ATTRIBUTE_GAP":
        missing_keys = []
        if intent.get("fit"):
            missing_keys.append(f"fit='{intent.get('fit')}'")
        if intent.get("color"):
            missing_keys.append(f"color='{intent.get('color')}'")
        if intent.get("material"):
            missing_keys.append(f"material='{intent.get('material')}'")
            
        attr_hint = f" ({', '.join(missing_keys)})" if missing_keys else ""
        return (
            f"Enrich metadata on {affected} relevant catalog items with missing query attributes{attr_hint} "
            f"to raise discovery coverage from {int(coverage * 100)}% to 100%."
        )
    elif root_cause == "INVENTORY_GAP":
        target_cat = intent.get("category", "this category")
        target_gender = intent.get("gender", "")
        return (
            f"Procure/onboard {target_gender} {target_cat} inventory. High search volume exists "
            f"with fewer than 4 matching items in the active catalog."
        )
    else:
        return f"Healthy discovery ({int(coverage * 100)}% coverage). Monitor conversion and customer review ratings."
