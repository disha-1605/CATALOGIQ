"""SQLAlchemy database models for CatalogIQ."""

from sqlalchemy import Column, String, Integer, Float, Text
from backend.database import Base


class Product(Base):
    """Product model representing catalog items with health scoring metrics."""
    __tablename__ = "products"

    product_id = Column(String(50), primary_key=True, index=True)
    brand = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    subcategory = Column(String(100), nullable=False)
    gender = Column(String(50), nullable=False, index=True)
    color = Column(String(50), nullable=True)
    material = Column(String(50), nullable=True)
    fit = Column(String(50), nullable=True)
    sleeve = Column(String(50), nullable=True)
    pattern = Column(String(50), nullable=True)
    price = Column(Float, nullable=False)

    # Computed Health Score Metrics
    health_score = Column(Float, nullable=False, default=0.0)
    health_classification = Column(String(50), nullable=False, default="Critical")
    attribute_completeness_score = Column(Float, nullable=False, default=0.0)
    title_quality_score = Column(Float, nullable=False, default=0.0)
    description_quality_score = Column(Float, nullable=False, default=0.0)
    category_consistency_score = Column(Float, nullable=False, default=0.0)
    missing_attributes = Column(Text, nullable=True)  # JSON string array
    quality_issues = Column(Text, nullable=True)  # JSON string array


class SearchQuery(Base):
    """Search query model representing customer queries and root cause analysis."""
    __tablename__ = "searches"

    query_id = Column(String(50), primary_key=True, index=True)
    query = Column(String(255), nullable=False, index=True)
    impressions = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    orders = Column(Integer, nullable=False, default=0)
    ctr = Column(Float, nullable=False, default=0.0)
    conversion_rate = Column(Float, nullable=False, default=0.0)

    # Intent and Diagnostic Results
    extracted_intent = Column(Text, nullable=False)  # JSON string dict
    relevant_products_count = Column(Integer, nullable=False, default=0)
    correctly_matching_count = Column(Integer, nullable=False, default=0)
    catalog_coverage = Column(Float, nullable=False, default=0.0)
    root_cause = Column(String(50), nullable=False, default="NO_CATALOG_GAP_DETECTED")
    affected_products_count = Column(Integer, nullable=False, default=0)
    missing_attributes_breakdown = Column(Text, nullable=True)  # JSON string dict

    # Opportunity Score & Sub-scores
    opportunity_score = Column(Float, nullable=False, default=0.0)
    demand_score = Column(Float, nullable=False, default=0.0)
    friction_score = Column(Float, nullable=False, default=0.0)
    gap_score = Column(Float, nullable=False, default=0.0)
    fixability_score = Column(Float, nullable=False, default=0.0)
    recommended_action = Column(Text, nullable=False, default="")
