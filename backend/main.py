"""FastAPI Application for CatalogIQ Backend."""

import json
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func

from backend.database import get_db, init_db
from backend.models import Product, SearchQuery
from backend.schemas import (
    ProductResponse,
    ProductDetailResponse,
    ProductListResponse,
    ProductHealthBreakdown,
    SearchQueryResponse,
    SearchQueryDetailResponse,
    SearchListResponse,
    SearchOpportunityScores,
    OpportunityItem,
    DashboardMetrics,
    ExplainRequest,
    ExplainResponse,
)
from backend.scoring import evaluate_product_health
from backend.llm_explainer import generate_llm_explanation


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database tables exist on startup."""
    init_db()
    yield


app = FastAPI(
    title="CatalogIQ API",
    description="Product Intelligence and Catalog Diagnostic Engine for Fashion E-Commerce",
    version="1.0.0",
    lifespan=lifespan,
)

# NOTE: CORS is temporarily configured to allow all origins ('*') for frontend development & testing.
# This will be tightened to specific production origin URLs once the frontend deployment host is provisioned.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _format_product(prod: Product) -> Dict[str, Any]:
    """Helper to convert SQLAlchemy Product model to schema dict."""
    missing_attrs = json.loads(prod.missing_attributes) if prod.missing_attributes else []
    quality_issues = json.loads(prod.quality_issues) if prod.quality_issues else []
    
    return {
        "product_id": prod.product_id,
        "brand": prod.brand,
        "title": prod.title,
        "description": prod.description,
        "category": prod.category,
        "subcategory": prod.subcategory,
        "gender": prod.gender,
        "color": prod.color,
        "material": prod.material,
        "fit": prod.fit,
        "sleeve": prod.sleeve,
        "pattern": prod.pattern,
        "price": prod.price,
        "health_score": prod.health_score,
        "health_classification": prod.health_classification,
        "attribute_completeness_score": prod.attribute_completeness_score,
        "title_quality_score": prod.title_quality_score,
        "description_quality_score": prod.description_quality_score,
        "category_consistency_score": prod.category_consistency_score,
        "missing_attributes": missing_attrs,
        "quality_issues": quality_issues,
    }


def _format_search(search: SearchQuery) -> Dict[str, Any]:
    """Helper to convert SQLAlchemy SearchQuery model to schema dict."""
    intent_dict = json.loads(search.extracted_intent) if search.extracted_intent else {}
    return {
        "query_id": search.query_id,
        "query": search.query,
        "search_volume": search.impressions,
        "clicks": search.clicks,
        "orders": search.orders,
        "ctr": search.ctr,
        "conversion_rate": search.conversion_rate,
        "relevant_products": search.relevant_products_count,
        "correctly_matching_products": search.correctly_matching_count,
        "catalog_coverage": search.catalog_coverage,
        "root_cause": search.root_cause,
        "opportunity_score": search.opportunity_score,
        "affected_products": search.affected_products_count,
        "extracted_intent": intent_dict,
        "recommended_action": search.recommended_action,
    }


# ==========================================
# 1. Dashboard Endpoint
# ==========================================

@app.get("/api/dashboard", response_model=DashboardMetrics, tags=["Dashboard"])
def get_dashboard(db: Session = Depends(get_db)):
    """
    Get high-level summary metrics, catalog health distribution,
    root-cause breakdown, and top priority opportunities.
    """
    total_products = db.query(Product).count()
    if total_products == 0:
        raise HTTPException(
            status_code=404,
            detail="Catalog dataset is empty. Run 'python -m backend.seed_data' to initialize."
        )

    avg_health = db.query(func.avg(Product.health_score)).scalar() or 0.0
    
    # Health distribution
    health_dist = {
        "Excellent": db.query(Product).filter(Product.health_classification == "Excellent").count(),
        "Good": db.query(Product).filter(Product.health_classification == "Good").count(),
        "Needs Attention": db.query(Product).filter(Product.health_classification == "Needs Attention").count(),
        "Critical": db.query(Product).filter(Product.health_classification == "Critical").count(),
    }
    
    # Search metrics
    searches = db.query(SearchQuery).all()
    total_searches = len(searches)
    total_volume = sum(s.impressions for s in searches)
    avg_ctr = (sum(s.ctr for s in searches) / total_searches) if total_searches > 0 else 0.0
    avg_cvr = (sum(s.conversion_rate for s in searches) / total_searches) if total_searches > 0 else 0.0
    
    # Root cause breakdown
    rc_counts = {
        "ATTRIBUTE_GAP": sum(1 for s in searches if s.root_cause == "ATTRIBUTE_GAP"),
        "INVENTORY_GAP": sum(1 for s in searches if s.root_cause == "INVENTORY_GAP"),
        "NO_CATALOG_GAP_DETECTED": sum(1 for s in searches if s.root_cause == "NO_CATALOG_GAP_DETECTED"),
    }
    
    # Top Opportunities sorted by opportunity_score desc
    top_search_records = db.query(SearchQuery).order_by(desc(SearchQuery.opportunity_score)).limit(5).all()
    top_opportunities = [
        OpportunityItem(
            query_id=s.query_id,
            query=s.query,
            opportunity_score=s.opportunity_score,
            root_cause=s.root_cause,
            search_volume=s.impressions,
            catalog_coverage=s.catalog_coverage,
            affected_products=s.affected_products_count,
            demand_score=s.demand_score,
            friction_score=s.friction_score,
            gap_score=s.gap_score,
            fixability_score=s.fixability_score,
            recommended_action=s.recommended_action,
        )
        for s in top_search_records
    ]
    
    return DashboardMetrics(
        total_products=total_products,
        average_health_score=round(avg_health, 1),
        health_distribution=health_dist,
        total_search_queries=total_searches,
        total_search_volume=total_volume,
        average_ctr=round(avg_ctr, 4),
        average_conversion_rate=round(avg_cvr, 4),
        root_cause_breakdown=rc_counts,
        top_opportunities=top_opportunities,
    )


# ==========================================
# 2. Products Endpoints
# ==========================================

@app.get("/api/products", response_model=ProductListResponse, tags=["Products"])
def list_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    health_classification: Optional[str] = Query(None, description="Filter by health tier"),
    q: Optional[str] = Query(None, description="Search by title or brand keyword"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List catalog products with filtering and pagination."""
    query = db.query(Product)
    
    if category:
        query = query.filter(Product.category.ilike(f"%{category}%"))
    if gender:
        query = query.filter(Product.gender.ilike(f"%{gender}%"))
    if health_classification:
        query = query.filter(Product.health_classification == health_classification)
    if q:
        search_filter = f"%{q}%"
        query = query.filter(
            (Product.title.ilike(search_filter)) | 
            (Product.brand.ilike(search_filter)) |
            (Product.description.ilike(search_filter))
        )
        
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return ProductListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[ProductResponse(**_format_product(p)) for p in items],
    )


@app.get("/api/products/{product_id}", response_model=ProductDetailResponse, tags=["Products"])
def get_product(product_id: str, db: Session = Depends(get_db)):
    """Get detailed product health analysis and recommendations for a single product."""
    prod = db.query(Product).filter(Product.product_id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail=f"Product with ID '{product_id}' not found.")
        
    prod_dict = _format_product(prod)
    
    # Generate live recommendations
    raw_eval = evaluate_product_health(prod_dict)
    
    breakdown = ProductHealthBreakdown(
        health_score=prod.health_score,
        health_classification=prod.health_classification,
        attribute_completeness=prod.attribute_completeness_score,
        title_quality=prod.title_quality_score,
        description_quality=prod.description_quality_score,
        category_consistency=prod.category_consistency_score,
        missing_attributes=prod_dict["missing_attributes"],
        quality_issues=prod_dict["quality_issues"],
    )
    
    return ProductDetailResponse(
        **prod_dict,
        health_breakdown=breakdown,
        recommendations=raw_eval.get("recommendations", []),
    )


# ==========================================
# 3. Searches Endpoints
# ==========================================

@app.get("/api/searches", response_model=SearchListResponse, tags=["Searches"])
def list_searches(
    root_cause: Optional[str] = Query(None, description="Filter by root cause (ATTRIBUTE_GAP, INVENTORY_GAP, NO_CATALOG_GAP_DETECTED)"),
    min_opportunity_score: Optional[float] = Query(None, ge=0.0, le=100.0),
    sort_by: str = Query("opportunity_score", description="Sort field: opportunity_score, search_volume, ctr, coverage"),
    order: str = Query("desc", description="Sort order: asc, desc"),
    db: Session = Depends(get_db),
):
    """List all search queries with intent, diagnostics, root causes, and opportunity scores."""
    query = db.query(SearchQuery)
    
    if root_cause:
        query = query.filter(SearchQuery.root_cause == root_cause)
    if min_opportunity_score is not None:
        query = query.filter(SearchQuery.opportunity_score >= min_opportunity_score)
        
    sort_column_map = {
        "opportunity_score": SearchQuery.opportunity_score,
        "search_volume": SearchQuery.impressions,
        "ctr": SearchQuery.ctr,
        "coverage": SearchQuery.catalog_coverage,
    }
    col = sort_column_map.get(sort_by, SearchQuery.opportunity_score)
    query = query.order_by(desc(col) if order == "desc" else asc(col))
    
    searches = query.all()
    return SearchListResponse(
        total=len(searches),
        items=[SearchQueryResponse(**_format_search(s)) for s in searches],
    )


@app.get("/api/searches/{query_id}", response_model=SearchQueryDetailResponse, tags=["Searches"])
def get_search_detail(query_id: str, db: Session = Depends(get_db)):
    """Get deep-dive diagnostics for a search query, including affected items and sub-scores."""
    search = db.query(SearchQuery).filter(SearchQuery.query_id == query_id).first()
    if not search:
        raise HTTPException(status_code=404, detail=f"Search query with ID '{query_id}' not found.")
        
    search_dict = _format_search(search)
    intent = search_dict["extracted_intent"]
    
    # Retrieve sample matching products
    category_target = intent.get("category")
    gender_target = intent.get("gender")
    
    prod_query = db.query(Product)
    if category_target:
        prod_query = prod_query.filter(Product.category == category_target)
    if gender_target and gender_target != "Unisex":
        prod_query = prod_query.filter(Product.gender.in_([gender_target, "Unisex"]))
        
    sample_prods = prod_query.limit(10).all()
    sample_prod_responses = [ProductResponse(**_format_product(p)) for p in sample_prods]
    
    missing_breakdown = {}
    if search.missing_attributes_breakdown:
        try:
            missing_breakdown = json.loads(search.missing_attributes_breakdown)
        except Exception:
            missing_breakdown = {}
            
    opp_scores = SearchOpportunityScores(
        demand_score=search.demand_score,
        friction_score=search.friction_score,
        gap_score=search.gap_score,
        fixability_score=search.fixability_score,
        opportunity_score=search.opportunity_score,
    )
    
    return SearchQueryDetailResponse(
        **search_dict,
        opportunity_scores=opp_scores,
        missing_attributes_breakdown=missing_breakdown,
        sample_relevant_products=sample_prod_responses,
    )


# ==========================================
# 4. Opportunities Endpoint
# ==========================================

@app.get("/api/opportunities", response_model=List[OpportunityItem], tags=["Opportunities"])
def list_opportunities(
    root_cause: Optional[str] = Query(None, description="Filter by root cause"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get prioritized list of search friction opportunities ranked by Opportunity Score (0-100).
    """
    query = db.query(SearchQuery)
    if root_cause:
        query = query.filter(SearchQuery.root_cause == root_cause)
        
    searches = query.order_by(desc(SearchQuery.opportunity_score)).limit(limit).all()
    
    return [
        OpportunityItem(
            query_id=s.query_id,
            query=s.query,
            opportunity_score=s.opportunity_score,
            root_cause=s.root_cause,
            search_volume=s.impressions,
            catalog_coverage=s.catalog_coverage,
            affected_products=s.affected_products_count,
            demand_score=s.demand_score,
            friction_score=s.friction_score,
            gap_score=s.gap_score,
            fixability_score=s.fixability_score,
            recommended_action=s.recommended_action,
        )
        for s in searches
    ]


# ==========================================
# 5. LLM Explanation Endpoint
# ==========================================

@app.post("/api/explain", response_model=ExplainResponse, tags=["Explanation"])
def explain_search_query(payload: ExplainRequest, db: Session = Depends(get_db)):
    """
    Generate plain-language executive explanation and recommended action
    for product managers based on deterministic diagnostic metrics.
    
    Tries live LLM API if configured; falls back reliably to deterministic template
    if API key is missing or request fails.
    """
    data_to_explain: Dict[str, Any] = {}
    query_id = payload.query_id

    if query_id:
        search = db.query(SearchQuery).filter(SearchQuery.query_id == query_id).first()
        if not search:
            raise HTTPException(status_code=404, detail=f"Search query with ID '{query_id}' not found.")
        data_to_explain = _format_search(search)
        if search.missing_attributes_breakdown:
            try:
                data_to_explain["missing_attributes_breakdown"] = json.loads(search.missing_attributes_breakdown)
            except Exception:
                data_to_explain["missing_attributes_breakdown"] = {}
    elif payload.query_data:
        data_to_explain = payload.query_data
        query_id = data_to_explain.get("query_id")
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'query_id' or 'query_data' object in request body."
        )

    explanation_result = generate_llm_explanation(data_to_explain)

    return ExplainResponse(
        query_id=query_id,
        query=data_to_explain.get("query", "Unknown Query"),
        root_cause=data_to_explain.get("root_cause", "NO_CATALOG_GAP_DETECTED"),
        opportunity_score=data_to_explain.get("opportunity_score", 0.0),
        explanation=explanation_result["explanation"],
        source=explanation_result["source"],
        model=explanation_result["model"],
    )

