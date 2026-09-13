"""FastAPI Application for CatalogIQ Backend."""

import json
import secrets
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func

from backend.database import get_db, init_db, SessionLocal
from backend.models import Product, SearchQuery, User, AccessRequest
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
    AccessRequestCreate,
    AccessRequestResponse,
    AccountActivationRequest,
    LoginRequest,
    AuthResponse,
    UserProfile,
    TestEmailRequest,
)
from backend.scoring import evaluate_product_health
from backend.llm_explainer import generate_llm_explanation
from backend.auth import (
    hash_password,
    verify_password,
    generate_secure_token,
    get_token_expiration,
    is_token_expired,
)
from backend.email_service import (
    send_email,
    build_admin_notification_email,
    build_requester_approved_email,
    build_admin_approved_confirmation_email,
    build_test_email,
    ADMIN_NOTIFICATION_EMAIL,
    API_BASE_URL,
    APP_BASE_URL,
)


def seed_admin_user():
    """Ensure the administrator user Disha (dishasengar1june@gmail.com) exists with PBKDF2 hash of 'tuffy'."""
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == "dishasengar1june@gmail.com").first()
        if not admin_user:
            admin_user = User(
                user_id="admin-disha-01",
                name="Disha",
                email="dishasengar1june@gmail.com",
                organization="CatalogIQ",
                role="Administrator",
                hashed_password=hash_password("tuffy"),
                is_active=1,
                is_admin=1,
                created_at=datetime.utcnow().isoformat(),
            )
            db.add(admin_user)
            db.commit()
        else:
            admin_user.is_admin = 1
            admin_user.is_active = 1
            admin_user.name = "Disha"
            admin_user.role = "Administrator"
            admin_user.organization = "CatalogIQ"
            admin_user.hashed_password = hash_password("tuffy")
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database tables exist, catalog/search data is seeded if empty, and admin user is seeded on startup."""
    init_db()

    # Check whether Product and SearchQuery data exist
    db = SessionLocal()
    try:
        prod_count = db.query(Product).count()
        query_count = db.query(SearchQuery).count()
        if prod_count == 0 or query_count == 0:
            from backend.seed_data import seed_database_and_csvs
            seed_database_and_csvs()
    finally:
        db.close()

    seed_admin_user()
    yield


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

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
        "image_url": prod.image_url,
        "injected_defect": prod.injected_defect,
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
        cat_clean = category.strip()
        cat_base = cat_clean.rstrip("sS") if len(cat_clean) > 3 and cat_clean.lower() != "dress" else cat_clean
        query = query.filter((Product.category.ilike(f"%{cat_clean}%")) | (Product.category.ilike(f"%{cat_base}%")))
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


# ==========================================
# 6. Authentication & Access Requests
# ==========================================

@app.post("/api/auth/login", response_model=AuthResponse, tags=["Auth"])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user. Supports both the demo admin account
    and real database-activated users.
    """
    email_clean = (payload.email or "").strip().lower()
    password_clean = payload.password or ""

    # 1. Demo Admin Account Check
    if email_clean == "admin@catalogiq.demo" and password_clean == "catalogiq123":
        return AuthResponse(
            success=True,
            user=UserProfile(
                user_id="admin-01",
                name="Adarsh",
                email="admin@catalogiq.demo",
                organization="CatalogIQ",
                role="Catalog Manager",
                is_admin=True,
            ),
            token="demo-session-token",
            message="Logged in successfully as Demo Administrator.",
        )

    # 2. Database User Check
    user = db.query(User).filter(User.email == email_clean, User.is_active == 1).first()
    if user and verify_password(password_clean, user.hashed_password):
        return AuthResponse(
            success=True,
            user=UserProfile(
                user_id=user.user_id,
                name=user.name,
                email=user.email,
                organization=user.organization,
                role=user.role,
                is_admin=bool(user.is_admin),
            ),
            token=f"sess-{secrets.token_hex(16)}",
            message="Logged in successfully.",
        )

    raise HTTPException(status_code=401, detail="Invalid email or password.")


@app.post("/api/access-requests", tags=["Access Requests"])
def create_access_request(payload: AccessRequestCreate, db: Session = Depends(get_db)):
    """
    Submit a new enterprise access request.
    Generates a secure single-use approval token and dispatches a notification email to the admin.
    """
    name_clean = payload.name.strip()
    email_clean = payload.email.strip().lower()
    org_clean = payload.organization.strip()
    role_clean = (payload.role or "Catalog Operations").strip()

    # Check if active user already exists
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    # Check if there is already a pending request
    existing_pending = db.query(AccessRequest).filter(
        AccessRequest.email == email_clean,
        AccessRequest.status == "PENDING"
    ).first()
    if existing_pending:
        return {
            "success": True,
            "message": "An access request for this email is already pending review.",
            "request_id": existing_pending.request_id,
            "status": "PENDING",
        }

    request_id = f"REQ-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    approval_token = generate_secure_token()
    token_expires_at = get_token_expiration(48)
    now_iso = datetime.utcnow().isoformat()
    now_formatted = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    new_req = AccessRequest(
        request_id=request_id,
        name=name_clean,
        email=email_clean,
        organization=org_clean,
        role=role_clean,
        status="PENDING",
        approval_token=approval_token,
        activation_token=None,
        token_expires_at=token_expires_at,
        created_at=now_iso,
        approved_at=None,
        approved_by=None,
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)

    # Build approval & reject URLs
    approval_url = f"{API_BASE_URL}/api/access-requests/{request_id}/approve?token={approval_token}"
    reject_url = f"{API_BASE_URL}/api/access-requests/{request_id}/reject?token={approval_token}"

    # Build and dispatch Admin Email
    html_body, text_body = build_admin_notification_email(
        name=name_clean,
        email=email_clean,
        organization=org_clean,
        role=role_clean,
        request_id=request_id,
        approval_url=approval_url,
        reject_url=reject_url,
        created_at_formatted=now_formatted,
    )
    email_res = send_email(
        to=ADMIN_NOTIFICATION_EMAIL,
        subject="CatalogIQ — New Access Request",
        html=html_body,
        text=text_body,
    )

    return {
        "success": True,
        "message": "Access request submitted successfully.",
        "request_id": request_id,
        "email_delivery": email_res.get("message", "Dispatched"),
    }


@app.get("/api/access-requests/{request_id}/approve", response_class=HTMLResponse, tags=["Access Requests"])
def approve_access_request(request_id: str, token: str = Query(...), db: Session = Depends(get_db)):
    """
    Secure admin action to approve an access request.
    Validates token, updates status to APPROVED, creates activation token,
    and sends the access-granted activation email to the requester.
    """
    req = db.query(AccessRequest).filter(AccessRequest.request_id == request_id).first()
    if not req:
        return HTMLResponse(
            status_code=404,
            content=_render_action_page(
                title="Request Not Found",
                status_badge="NOT FOUND",
                badge_color="#9B1C1C",
                heading="Access Request Not Found",
                message=f"No access request matching ID '{request_id}' was found.",
            )
        )

    # Check token match
    if req.approval_token != token:
        return HTMLResponse(
            status_code=403,
            content=_render_action_page(
                title="Invalid Approval Link",
                status_badge="SECURITY ERROR",
                badge_color="#9B1C1C",
                heading="Invalid or Expired Approval Link",
                message="This approval link is invalid, has already been used, or the token does not match.",
            )
        )

    # Check expiration
    if is_token_expired(req.token_expires_at):
        return HTMLResponse(
            status_code=400,
            content=_render_action_page(
                title="Link Expired",
                status_badge="EXPIRED",
                badge_color="#9B1C1C",
                heading="Approval Link Has Expired",
                message="This single-use approval link has expired (valid for 48 hours). Please request a new submission.",
            )
        )

    # Check status
    if req.status != "PENDING":
        return HTMLResponse(
            status_code=400,
            content=_render_action_page(
                title="Already Processed",
                status_badge="PROCESSED",
                badge_color="#1E40AF",
                heading=f"Request Already {req.status}",
                message=f"This access request has already been marked as {req.status} on {req.approved_at or 'a previous date'}.",
            )
        )

    # Approve request and generate single-use activation token
    activation_token = generate_secure_token()
    token_expires_at = get_token_expiration(48)
    now_iso = datetime.utcnow().isoformat()
    now_formatted = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    req.status = "APPROVED"
    req.approved_at = now_iso
    req.approved_by = "Disha"
    req.activation_token = activation_token
    req.token_expires_at = token_expires_at
    req.approval_token = None  # Invalidate approval token (single-use)
    db.commit()

    # Build activation URL & send requester email
    activation_url = f"{APP_BASE_URL}/activate.html?token={activation_token}"
    req_html, req_text = build_requester_approved_email(
        name=req.name,
        organization=req.organization,
        role=req.role or "Catalog Operations",
        activation_url=activation_url,
    )
    requester_email_result = send_email(
        to=req.email,
        subject="CatalogIQ — Your Access Has Been Approved",
        html=req_html,
        text=req_text,
    )

    print(f"[CATALOGIQ] Requester activation email result: {requester_email_result}")

    # Send confirmation to admin
    admin_html, admin_text = build_admin_approved_confirmation_email(
        name=req.name,
        email=req.email,
        organization=req.organization,
        approved_at_formatted=now_formatted,
    )
    send_email(
        to=ADMIN_NOTIFICATION_EMAIL,
        subject="CatalogIQ — Access Request Approved",
        html=admin_html,
        text=admin_text,
    )

    return HTMLResponse(
        content=_render_action_page(
            title="Access Granted",
            status_badge="ACCESS GRANTED",
            badge_color="#03543F",
            heading="Access Approved Successfully",
            message=f"Access for <strong>{req.name}</strong> ({req.organization}) has been approved.<br/><br/>An activation email with password setup instructions has been dispatched to <code style='background:#F3F4F6; padding:2px 6px; border-radius:4px;'>{req.email}</code>.",
            action_btn_text="Return to CatalogIQ",
            action_btn_url=f"{APP_BASE_URL}/dashboard.html",
        )
    )


@app.get("/api/access-requests/{request_id}/reject", response_class=HTMLResponse, tags=["Access Requests"])
def reject_access_request(request_id: str, token: str = Query(...), db: Session = Depends(get_db)):
    """Decline an access request."""
    req = db.query(AccessRequest).filter(AccessRequest.request_id == request_id).first()
    if not req or req.approval_token != token:
        return HTMLResponse(
            status_code=403,
            content=_render_action_page(
                title="Invalid Link",
                status_badge="ERROR",
                badge_color="#9B1C1C",
                heading="Invalid Link",
                message="This decline link is invalid or has already been used.",
            )
        )

    if req.status != "PENDING":
        return HTMLResponse(
            status_code=400,
            content=_render_action_page(
                title="Already Processed",
                status_badge="PROCESSED",
                badge_color="#1E40AF",
                heading=f"Request Already {req.status}",
                message=f"This request has already been marked as {req.status}.",
            )
        )

    req.status = "REJECTED"
    req.approval_token = None
    req.approved_at = datetime.utcnow().isoformat()
    req.approved_by = "Disha"
    db.commit()

    return HTMLResponse(
        content=_render_action_page(
            title="Request Declined",
            status_badge="DECLINED",
            badge_color="#9B1C1C",
            heading="Access Request Declined",
            message=f"The access request for {req.name} ({req.email}) has been marked as declined.",
            action_btn_text="Return to CatalogIQ",
            action_btn_url=f"{APP_BASE_URL}/dashboard.html",
        )
    )


@app.get("/api/access-requests/validate-activation", tags=["Access Requests"])
def validate_activation_token(token: str = Query(...), db: Session = Depends(get_db)):
    """Validate activation token for frontend activate.html page."""
    req = db.query(AccessRequest).filter(
        AccessRequest.activation_token == token,
        AccessRequest.status == "APPROVED"
    ).first()
    if not req:
        raise HTTPException(status_code=400, detail="Invalid or expired activation link.")
    if is_token_expired(req.token_expires_at):
        raise HTTPException(status_code=400, detail="This activation link has expired (48 hours validity).")

    return {
        "valid": True,
        "name": req.name,
        "email": req.email,
        "organization": req.organization,
        "role": req.role,
    }


@app.post("/api/access-requests/activate", tags=["Access Requests"])
def activate_account(payload: AccountActivationRequest, db: Session = Depends(get_db)):
    """
    Set password and activate account for approved requester.
    """
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    req = db.query(AccessRequest).filter(
        AccessRequest.activation_token == payload.token,
        AccessRequest.status == "APPROVED"
    ).first()
    if not req:
        raise HTTPException(status_code=400, detail="Invalid or expired activation token.")
    if is_token_expired(req.token_expires_at):
        raise HTTPException(status_code=400, detail="Activation token has expired.")

    # Create active user account
    user_id = f"USR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2)}"
    hashed_pw = hash_password(payload.password)

    user = User(
        user_id=user_id,
        email=req.email.lower(),
        name=req.name,
        organization=req.organization,
        role=req.role or "Catalog Specialist",
        hashed_password=hashed_pw,
        is_active=1,
        is_admin=0,
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(user)

    # Invalidate activation token
    req.activation_token = None
    db.commit()

    return {
        "success": True,
        "message": "Account activated successfully. You can now sign in.",
        "email": req.email,
    }


@app.get("/api/access-requests", response_model=List[AccessRequestResponse], tags=["Access Requests"])
def list_access_requests(db: Session = Depends(get_db)):
    """List all access requests (admin view)."""
    return db.query(AccessRequest).order_by(desc(AccessRequest.created_at)).all()


@app.post("/api/admin/test-email", tags=["Administration"])
def test_email_delivery(payload: Optional[TestEmailRequest] = None):
    """
    Safe administrative delivery test endpoint.
    Dispatches a live test email to the designated recipient and returns explicit SMTP diagnostic status.
    """
    recipient = (payload.recipient if payload and payload.recipient else "dishasengar1june@gmail.com").strip()
    now_formatted = datetime.utcnow().strftime("%d %b %Y, %H:%M:%S UTC")
    html_body, text_body = build_test_email(recipient, now_formatted)
    
    result = send_email(
        to=recipient,
        subject="CatalogIQ — Email Delivery Test",
        html=html_body,
        text=text_body,
    )
    return result


def _render_action_page(
    title: str,
    status_badge: str,
    badge_color: str,
    heading: str,
    message: str,
    action_btn_text: Optional[str] = None,
    action_btn_url: Optional[str] = None,
) -> str:
    """Helper to render branded standalone HTML confirmation cards for email action redirects."""
    btn_html = ""
    if action_btn_text and action_btn_url:
        btn_html = f"""
          <div style="margin-top: 28px;">
            <a href="{action_btn_url}" style="display:inline-block; background-color:#101827; color:#FFFFFF; text-decoration:none; font-weight:600; font-size:14px; padding:12px 28px; border-radius:10px;">
              {action_btn_text} →
            </a>
          </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en" style="height:100%; background:#FBF7F3;">
<head>
  <meta charset="utf-8">
  <title>{title} — CatalogIQ</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ margin:0; padding:20px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display:flex; align-items:center; justify-content:center; min-height:100vh; box-sizing:border-box; background:#FBF7F3; }}
    .card {{ max-width:540px; width:100%; background:#FFFFFF; border-radius:18px; border:1px solid #E5E0DA; padding:36px; box-shadow:0 8px 24px rgba(16,24,39,0.06); text-align:center; }}
    .brand {{ display:inline-flex; align-items:center; gap:10px; margin-bottom:24px; }}
    .logo-badge {{ width:32px; height:32px; line-height:32px; background:#E83E4F; color:#FFFFFF; font-weight:bold; font-size:16px; border-radius:8px; }}
    .brand-name {{ font-size:18px; font-weight:bold; color:#101827; }}
    .badge {{ display:inline-block; padding:4px 12px; border-radius:6px; font-size:11px; font-family:monospace; font-weight:bold; letter-spacing:0.05em; color:#FFFFFF; background:{badge_color}; margin-bottom:16px; }}
    h1 {{ font-size:22px; color:#101827; margin:0 0 12px 0; }}
    p {{ font-size:14px; color:#4B5563; line-height:1.6; margin:0; }}
    .footer {{ margin-top:32px; padding-top:20px; border-top:1px solid #EFECE6; font-size:11px; font-family:monospace; color:#9CA3AF; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <div class="logo-badge">Q</div>
      <span class="brand-name">CatalogIQ</span>
    </div>
    <div>
      <span class="badge">{status_badge}</span>
      <h1>{heading}</h1>
      <p>{message}</p>
      {btn_html}
    </div>
    <div class="footer">
      CatalogIQ Enterprise Intelligence Platform · v1.0
    </div>
  </div>
</body>
</html>"""


# =============================================================================
# FRONTEND STATIC FILES & ROOT ROUTE
# Mounted after all /api/* routes so API routes always take precedence.
# =============================================================================

@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to login page."""
    return RedirectResponse(url="/login.html")


if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )



