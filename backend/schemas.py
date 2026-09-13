"""Pydantic data validation and serialization schemas for CatalogIQ."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# --- Product Schemas ---

class ProductHealthBreakdown(BaseModel):
    """Detailed breakdown of a product's health score components."""
    health_score: float = Field(..., description="Overall health score (0-100)")
    health_classification: str = Field(..., description="Classification: Excellent, Good, Needs Attention, Critical")
    attribute_completeness: float = Field(..., description="Attribute completeness sub-score (0-100)")
    title_quality: float = Field(..., description="Title quality sub-score (0-100)")
    description_quality: float = Field(..., description="Description quality sub-score (0-100)")
    category_consistency: float = Field(..., description="Category consistency sub-score (0-100)")
    missing_attributes: List[str] = Field(default_factory=list, description="List of unpopulated expected attributes")
    quality_issues: List[str] = Field(default_factory=list, description="List of detected defect warnings")


class ProductBase(BaseModel):
    product_id: str
    brand: str
    title: str
    description: str
    category: str
    subcategory: str
    gender: str
    color: Optional[str] = None
    material: Optional[str] = None
    fit: Optional[str] = None
    sleeve: Optional[str] = None
    pattern: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    injected_defect: Optional[str] = None


class ProductResponse(ProductBase):
    health_score: float
    health_classification: str
    attribute_completeness_score: float
    title_quality_score: float
    description_quality_score: float
    category_consistency_score: float
    missing_attributes: List[str] = Field(default_factory=list)
    quality_issues: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProductDetailResponse(ProductResponse):
    health_breakdown: ProductHealthBreakdown
    recommendations: List[str] = Field(default_factory=list)


class ProductListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ProductResponse]


# --- Search Schemas ---

class SearchIntent(BaseModel):
    """Extracted query intent attributes."""
    gender: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    fit: Optional[str] = None
    sleeve: Optional[str] = None
    pattern: Optional[str] = None
    raw_tokens: List[str] = Field(default_factory=list)


class SearchQueryResponse(BaseModel):
    query_id: str
    query: str
    search_volume: int = Field(..., description="Search volume / impressions")
    clicks: int
    orders: int
    ctr: float
    conversion_rate: float
    relevant_products: int
    correctly_matching_products: int
    catalog_coverage: float
    root_cause: str
    opportunity_score: float
    affected_products: int
    extracted_intent: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: str

    model_config = ConfigDict(from_attributes=True)


class SearchOpportunityScores(BaseModel):
    demand_score: float
    friction_score: float
    gap_score: float
    fixability_score: float
    opportunity_score: float


class SearchQueryDetailResponse(SearchQueryResponse):
    opportunity_scores: SearchOpportunityScores
    missing_attributes_breakdown: Dict[str, int] = Field(default_factory=dict)
    sample_relevant_products: List[ProductResponse] = Field(default_factory=list)


class SearchListResponse(BaseModel):
    total: int
    items: List[SearchQueryResponse]


# --- Opportunity & Dashboard Schemas ---

class OpportunityItem(BaseModel):
    query_id: str
    query: str
    opportunity_score: float
    root_cause: str
    search_volume: int
    catalog_coverage: float
    affected_products: int
    demand_score: float
    friction_score: float
    gap_score: float
    fixability_score: float
    recommended_action: str


class DashboardMetrics(BaseModel):
    total_products: int
    average_health_score: float
    health_distribution: Dict[str, int]
    total_search_queries: int
    total_search_volume: int
    average_ctr: float
    average_conversion_rate: float
    root_cause_breakdown: Dict[str, int]
    top_opportunities: List[OpportunityItem]


# --- Explanation Schemas ---

class ExplainRequest(BaseModel):
    """Request payload for generating an explanation."""
    query_id: Optional[str] = Field(None, description="ID of existing search query to explain (e.g. Q001)")
    query_data: Optional[Dict[str, Any]] = Field(None, description="Optional full search analysis object if explaining ad-hoc query")


class ExplainResponse(BaseModel):
    """Plain-language explanation response."""
    query_id: Optional[str] = None
    query: str
    root_cause: str
    opportunity_score: float
    explanation: str
    source: str = Field(..., description="'llm' if generated by live model, 'template_fallback' if deterministic fallback")
    model: str


# --- Access Request & Auth Schemas ---

class AccessRequestCreate(BaseModel):
    """Payload for submitting a new access request."""
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    organization: str = Field(..., min_length=2, max_length=150)
    role: Optional[str] = Field(default="Catalog Operations", max_length=100)


class AccessRequestResponse(BaseModel):
    request_id: str
    name: str
    email: str
    organization: str
    role: Optional[str] = None
    status: str
    created_at: str
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AccountActivationRequest(BaseModel):
    """Payload for activating an approved requester account."""
    token: str = Field(..., min_length=10)
    password: str = Field(..., min_length=6, max_length=128)
    confirm_password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """Payload for user authentication."""
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class UserProfile(BaseModel):
    user_id: str
    name: str
    email: str
    organization: str
    role: str
    is_admin: bool = False


class AuthResponse(BaseModel):
    success: bool
    user: Optional[UserProfile] = None
    token: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class TestEmailRequest(BaseModel):
    recipient: Optional[str] = Field(default="dishasengar1june@gmail.com")

