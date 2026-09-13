"""Tests for Production Deployment: Static Frontend Serving and Startup Seeding."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import Product, SearchQuery, User

client = TestClient(app)


def test_root_redirects_to_login():
    """Verify GET / returns a redirect to /login.html."""
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (307, 302, 301)
    assert res.headers["location"] == "/login.html"


def test_static_frontend_pages_served():
    """Verify FastAPI StaticFiles serves frontend HTML files with HTTP 200."""
    login_res = client.get("/login.html")
    assert login_res.status_code == 200
    assert "CatalogIQ" in login_res.text
    assert "Request access" in login_res.text

    dashboard_res = client.get("/dashboard.html")
    assert dashboard_res.status_code == 200
    assert "CatalogIQ" in dashboard_res.text
    assert "Needs Attention" in dashboard_res.text

    search_intel_res = client.get("/search-intelligence.html")
    assert search_intel_res.status_code == 200

    product_audit_res = client.get("/product-audit.html")
    assert product_audit_res.status_code == 200


def test_startup_database_seeded_with_catalog_and_searches():
    """Verify the database contains 200 products and 40 searches."""
    db = SessionLocal()
    try:
        product_count = db.query(Product).count()
        query_count = db.query(SearchQuery).count()
        assert product_count == 200, f"Expected 200 products, got {product_count}"
        assert query_count == 40, f"Expected 40 search queries, got {query_count}"
    finally:
        db.close()


def test_api_dashboard_contains_seeded_data():
    """Verify GET /api/dashboard returns HTTP 200 and reflects 200 products / 40 queries."""
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["total_products"] == 200
    assert data["total_search_queries"] == 40
    assert data["total_search_volume"] > 0
    assert "health_distribution" in data
    assert "top_opportunities" in data


def test_api_products_endpoint():
    """Verify GET /api/products returns HTTP 200 and paginated list of products."""
    res = client.get("/api/products?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 200
    assert len(data["items"]) == 10


def test_api_precedence_over_static():
    """Verify API endpoints take precedence over static file routing."""
    res = client.get("/api/opportunities")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
