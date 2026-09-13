"""Tests for Access Request, Admin Approval, Activation, and Authentication Flows."""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app, seed_admin_user
from backend.database import SessionLocal
from backend.models import AccessRequest, User
from backend.auth import hash_password, verify_password, generate_secure_token
from backend.email_service import is_smtp_configured, send_email

from unittest.mock import patch

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_send_email_fixture():
    """Mock email delivery to avoid external SMTP calls during test execution."""
    with patch("backend.main.send_email") as mock_mail:
        mock_mail.return_value = {
            "success": True,
            "mode": "smtp",
            "recipient": "dishasengar1june@gmail.com",
            "smtp_connection": "PASS",
            "smtp_authentication": "PASS",
            "message_accepted": "PASS",
            "error_type": None,
            "safe_error_message": None,
            "message": "Mock email sent"
        }
        yield mock_mail


@pytest.fixture(autouse=True)
def setup_and_cleanup_test_records():
    """Ensure admin user is seeded and clean up test access requests/users."""
    seed_admin_user()
    db = SessionLocal()
    try:
        db.query(AccessRequest).filter(AccessRequest.email.like("%testuser%")).delete()
        db.query(User).filter(User.email.like("%testuser%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AccessRequest).filter(AccessRequest.email.like("%testuser%")).delete()
        db.query(User).filter(User.email.like("%testuser%")).delete()
        db.commit()
    finally:
        db.close()



def test_disha_admin_login():
    """Verify administrator Disha (dishasengar1june@gmail.com / tuffy) logs in with admin rights."""
    res = client.post("/api/auth/login", json={
        "email": "dishasengar1june@gmail.com",
        "password": "tuffy"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["user"]["name"] == "Disha"
    assert data["user"]["email"] == "dishasengar1june@gmail.com"
    assert data["user"]["role"] == "Administrator"
    assert data["user"]["organization"] == "CatalogIQ"
    assert data["user"]["is_admin"] is True

    # Verify password is not stored in plaintext in DB
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "dishasengar1june@gmail.com").first()
        assert user is not None
        assert user.hashed_password != "tuffy"
        assert "$" in user.hashed_password
        assert verify_password("tuffy", user.hashed_password) is True
    finally:
        db.close()


def test_admin_demo_login():
    """Verify demo admin credentials (admin@catalogiq.demo / catalogiq123) authenticate properly."""
    res = client.post("/api/auth/login", json={
        "email": "admin@catalogiq.demo",
        "password": "catalogiq123"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["user"]["name"] == "Adarsh"
    assert data["user"]["role"] == "Catalog Manager"
    assert data["user"]["is_admin"] is True


def test_invalid_login_credentials():
    """Verify invalid credentials return 401."""
    res = client.post("/api/auth/login", json={
        "email": "admin@catalogiq.demo",
        "password": "wrongpassword"
    })
    assert res.status_code == 401
    assert "Invalid email or password." in res.json()["detail"]

    res2 = client.post("/api/auth/login", json={
        "email": "dishasengar1june@gmail.com",
        "password": "wrongpassword"
    })
    assert res2.status_code == 401

    res3 = client.post("/api/auth/login", json={
        "email": "nonexistent@demo.com",
        "password": "catalogiq123"
    })
    assert res3.status_code == 401


def test_forgot_password_ui_removed():
    """Verify that 'Forgot password?' is completely removed from login.html."""
    login_html_path = Path("/Users/disha/Desktop/CatalogIQ/frontend/login.html")
    assert login_html_path.exists()
    content = login_html_path.read_text(encoding="utf-8")
    assert "Forgot password?" not in content
    assert "forgot-password" not in content.lower()


def test_password_hashing_and_verification():
    """Verify cryptographic password hashing works correctly."""
    plain = "SecurePass123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert "$" in hashed
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_access_request_validation():
    """Verify validation on required fields for access requests."""
    # Missing name
    res = client.post("/api/access-requests", json={
        "name": "",
        "email": "testuser1@company.demo",
        "organization": "Test Corp"
    })
    assert res.status_code == 422


def test_full_access_request_approval_and_activation_flow():
    """End-to-end test of access request -> approval -> activation -> login."""
    test_email = "testuser_e2e@company.demo"
    test_name = "E2E Requester"
    test_org = "E2E Fashion Brand"
    test_role = "Senior Catalog Specialist"
    new_password = "E2EPassword2026!"

    # 1. Submit Access Request
    req_res = client.post("/api/access-requests", json={
        "name": test_name,
        "email": test_email,
        "organization": test_org,
        "role": test_role
    })
    assert req_res.status_code == 200
    req_data = req_res.json()
    assert req_data["success"] is True
    request_id = req_data["request_id"]
    assert request_id.startswith("REQ-")

    # Inspect database for pending record and approval token
    db = SessionLocal()
    db_req = db.query(AccessRequest).filter(AccessRequest.request_id == request_id).first()
    assert db_req is not None
    assert db_req.status == "PENDING"
    approval_token = db_req.approval_token
    assert approval_token is not None
    db.close()

    # 2. Test Invalid Approval Token
    bad_approve_res = client.get(f"/api/access-requests/{request_id}/approve?token=tampered_token")
    assert bad_approve_res.status_code == 403

    # 3. Approve Access Request with Valid Token
    approve_res = client.get(f"/api/access-requests/{request_id}/approve?token={approval_token}")
    assert approve_res.status_code == 200
    assert "Access Approved Successfully" in approve_res.text

    # Verify status in database
    db = SessionLocal()
    db_req = db.query(AccessRequest).filter(AccessRequest.request_id == request_id).first()
    assert db_req.status == "APPROVED"
    assert db_req.approved_by == "Disha"
    assert db_req.approval_token is None  # Single-use token invalidated
    activation_token = db_req.activation_token
    assert activation_token is not None
    db.close()

    # 4. Test Duplicate Approval Attempt (Must be rejected)
    dup_res = client.get(f"/api/access-requests/{request_id}/approve?token={approval_token}")
    assert dup_res.status_code in (400, 403)

    # 5. Validate Activation Token
    val_res = client.get(f"/api/access-requests/validate-activation?token={activation_token}")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["valid"] is True
    assert val_data["email"] == test_email.lower()
    assert val_data["name"] == test_name

    # 6. Activate Account with Password
    act_res = client.post("/api/access-requests/activate", json={
        "token": activation_token,
        "password": new_password,
        "confirm_password": new_password
    })
    assert act_res.status_code == 200
    assert act_res.json()["success"] is True

    # 7. Verify Activation Token Cannot Be Reused
    act_res2 = client.post("/api/access-requests/activate", json={
        "token": activation_token,
        "password": "AnotherPassword!",
        "confirm_password": "AnotherPassword!"
    })
    assert act_res2.status_code == 400

    # 8. Login as newly activated user
    login_res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": new_password
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["success"] is True
    assert login_data["user"]["email"] == test_email.lower()
    assert login_data["user"]["name"] == test_name
    assert login_data["user"]["organization"] == test_org

    # 9. Ensure Demo Admin and Disha Admin Still Authenticate
    admin_login_res = client.post("/api/auth/login", json={
        "email": "admin@catalogiq.demo",
        "password": "catalogiq123"
    })
    assert admin_login_res.status_code == 200
    assert admin_login_res.json()["user"]["email"] == "admin@catalogiq.demo"

    disha_login_res = client.post("/api/auth/login", json={
        "email": "dishasengar1june@gmail.com",
        "password": "tuffy"
    })
    assert disha_login_res.status_code == 200
    assert disha_login_res.json()["user"]["email"] == "dishasengar1june@gmail.com"


def test_reject_access_request_flow():
    """Verify request rejection flow."""
    test_email = "testuser_reject@company.demo"
    req_res = client.post("/api/access-requests", json={
        "name": "Reject Requester",
        "email": test_email,
        "organization": "Declined Retail",
        "role": "Inventory Assistant"
    })
    request_id = req_res.json()["request_id"]

    db = SessionLocal()
    db_req = db.query(AccessRequest).filter(AccessRequest.request_id == request_id).first()
    approval_token = db_req.approval_token
    db.close()

    reject_res = client.get(f"/api/access-requests/{request_id}/reject?token={approval_token}")
    assert reject_res.status_code == 200
    assert "Declined" in reject_res.text

    db = SessionLocal()
    db_req = db.query(AccessRequest).filter(AccessRequest.request_id == request_id).first()
    assert db_req.status == "REJECTED"
    assert db_req.approved_by == "Disha"
    db.close()


def test_admin_email_test_endpoint():
    """Verify POST /api/admin/test-email endpoint returns honest delivery diagnostics."""
    res = client.post("/api/admin/test-email", json={
        "recipient": "dishasengar1june@gmail.com"
    })
    assert res.status_code == 200
    data = res.json()
    assert "recipient" in data
    assert data["recipient"] == "dishasengar1june@gmail.com"
    assert "smtp_connection" in data
    assert "message_accepted" in data
