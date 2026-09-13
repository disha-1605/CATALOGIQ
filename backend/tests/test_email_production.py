"""Unit and integration tests for production email delivery, diagnostics, and URL resolution."""

import os
import smtplib
import socket
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.email_service import (
    send_email,
    get_base_url,
    get_api_base_url,
    get_admin_notification_email,
    get_smtp_config,
    is_smtp_configured,
)
from backend.database import SessionLocal
from backend.models import AccessRequest, User

client = TestClient(app)



@pytest.fixture(autouse=True)
def setup_and_cleanup_test_records():
    """Clean up test access requests before and after test runs."""
    db = SessionLocal()
    try:
        db.query(AccessRequest).filter(AccessRequest.email.like("%test%")).delete()
        db.query(User).filter(User.email.like("%test%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AccessRequest).filter(AccessRequest.email.like("%test%")).delete()
        db.query(User).filter(User.email.like("%test%")).delete()
        db.commit()
    finally:
        db.close()



def test_smtp_configuration_missing_diagnostic():
    """Verify send_email returns structured not_configured when credentials missing."""
    with patch.dict(os.environ, {"SMTP_HOST": "", "SMTP_USERNAME": "", "SMTP_PASSWORD": ""}, clear=False):
        result = send_email("test@example.com", "Test Subject", "<p>HTML</p>", "Text")
        assert result["success"] is False
        assert result["mode"] == "not_configured"
        assert result["smtp_connection"] == "SKIPPED"
        assert result["smtp_authentication"] == "SKIPPED"
        assert result["message_accepted"] == "SKIPPED"
        assert result["error_type"] == "configuration_missing"
        assert "SMTP credentials" in result["safe_error_message"]
        # Ensure no secrets in output
        assert "password" not in str(result).lower() or "password" in result["safe_error_message"].lower()


def test_smtp_connection_failure_diagnostic():
    """Verify send_email reports connection failure safely when server is unreachable."""
    env_vars = {
        "SMTP_HOST": "unreachable.smtp.server",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "test@example.com",
        "SMTP_PASSWORD": "dummy_password",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        with patch("smtplib.SMTP", side_effect=socket.gaierror("Name or service not known")):
            result = send_email("test@example.com", "Test Subject", "<p>HTML</p>", "Text")
            assert result["success"] is False
            assert result["mode"] == "smtp_conn_error"
            assert result["smtp_connection"] == "FAIL"
            assert result["smtp_authentication"] == "SKIPPED"
            assert result["message_accepted"] == "FAIL"
            assert result["error_type"] == "connection_failure"
            assert "Could not connect to SMTP server" in result["safe_error_message"]
            # Ensure dummy_password is not in result
            assert "dummy_password" not in str(result)


def test_smtp_authentication_failure_diagnostic():
    """Verify send_email reports authentication failure safely when credentials rejected."""
    env_vars = {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "user@gmail.com",
        "SMTP_PASSWORD": "wrong_password",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        mock_smtp = MagicMock()
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
        with patch("smtplib.SMTP", return_value=mock_smtp):
            result = send_email("test@example.com", "Test Subject", "<p>HTML</p>", "Text")
            assert result["success"] is False
            assert result["mode"] == "smtp_auth_error"
            assert result["smtp_connection"] == "PASS"
            assert result["smtp_authentication"] == "FAIL"
            assert result["message_accepted"] == "FAIL"
            assert result["error_type"] == "authentication_failure"
            assert "Google App Password" in result["safe_error_message"]
            # Ensure password is never in result
            assert "wrong_password" not in str(result)


def test_smtp_message_accepted():
    """Verify send_email reports PASS on all checks when SMTP accepts message."""
    env_vars = {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "user@gmail.com",
        "SMTP_PASSWORD": "valid_app_password",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            result = send_email("test@example.com", "Test Subject", "<p>HTML</p>", "Text")
            assert result["success"] is True
            assert result["mode"] == "smtp"
            assert result["smtp_connection"] == "PASS"
            assert result["smtp_authentication"] == "PASS"
            assert result["message_accepted"] == "PASS"
            assert result["error_type"] is None
            assert result["safe_error_message"] is None
            assert mock_smtp.sendmail.called


def test_production_base_url_resolution():
    """Verify production base URL resolves properly with Render and production env."""
    with patch.dict(os.environ, {"APP_BASE_URL": "https://catalogiq-c4cr.onrender.com"}, clear=False):
        assert get_base_url() == "https://catalogiq-c4cr.onrender.com"
        assert get_api_base_url() == "https://catalogiq-c4cr.onrender.com"

    with patch.dict(os.environ, {"APP_BASE_URL": "", "RENDER_EXTERNAL_URL": "https://catalogiq-c4cr.onrender.com"}, clear=False):
        assert get_base_url() == "https://catalogiq-c4cr.onrender.com"

    with patch.dict(os.environ, {"APP_BASE_URL": "", "RENDER_EXTERNAL_URL": "", "APP_ENV": "production"}, clear=False):
        assert get_base_url() == "https://catalogiq-c4cr.onrender.com"


def test_admin_email_config_status_endpoint():
    """Verify GET /api/admin/email-config-status returns safe configuration booleans without secrets."""
    res = client.get("/api/admin/email-config-status")
    assert res.status_code == 200
    data = res.json()
    assert "smtp_host_configured" in data
    assert "smtp_port_configured" in data
    assert "smtp_username_configured" in data
    assert "smtp_password_configured" in data
    assert "email_from_configured" in data
    assert "admin_notification_email_configured" in data
    assert "admin_notification_email" in data
    assert "app_base_url" in data
    assert "api_base_url" in data
    # Ensure password values or secret keys are never present
    assert "smtp_password" not in data or isinstance(data.get("smtp_password"), bool)
    assert "password" not in data


def test_admin_test_email_endpoint_mocked():
    """Verify POST and GET /api/admin/test-email return safe diagnostic result."""
    with patch("backend.main.send_email") as mock_send:
        mock_send.return_value = {
            "success": True,
            "mode": "smtp",
            "recipient": "dishasengar1june@gmail.com",
            "smtp_connection": "PASS",
            "smtp_authentication": "PASS",
            "message_accepted": "PASS",
            "error_type": None,
            "safe_error_message": None,
            "message": "Email delivered to dishasengar1june@gmail.com via SMTP (smtp.gmail.com)"
        }
        post_res = client.post("/api/admin/test-email", json={"recipient": "dishasengar1june@gmail.com"})
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["success"] is True
        assert post_data["smtp_connection"] == "PASS"

        get_res = client.get("/api/admin/test-email")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["success"] is True


def test_request_access_dispatches_email_and_handles_url():
    """Verify Request Access flow generates production approval URLs and invokes send_email."""
    test_email = "prod_requester_test@company.demo"
    with patch.dict(os.environ, {"APP_BASE_URL": "https://catalogiq-c4cr.onrender.com", "API_BASE_URL": "https://catalogiq-c4cr.onrender.com"}, clear=False):
        with patch("backend.main.send_email") as mock_send:
            mock_send.return_value = {
                "success": True,
                "mode": "smtp",
                "recipient": "dishasengar1june@gmail.com",
                "smtp_connection": "PASS",
                "smtp_authentication": "PASS",
                "message_accepted": "PASS",
                "error_type": None,
                "safe_error_message": None,
                "message": "Email delivered"
            }
            res = client.post("/api/access-requests", json={
                "name": "Production Requester",
                "email": test_email,
                "organization": "Render Retail",
                "role": "Lead Architect"
            })
            assert res.status_code == 200
            assert mock_send.called
            # Verify the email content generated has the production URL
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["to"] == "dishasengar1june@gmail.com"
            assert "https://catalogiq-c4cr.onrender.com" in call_kwargs["html"]
            assert "localhost" not in call_kwargs["html"]


def test_grant_access_dispatches_requester_and_admin_emails():
    """Verify Grant Access approval generates production activation URL and dispatches both emails."""
    test_email = "approval_email_test@company.demo"
    with patch.dict(os.environ, {"APP_BASE_URL": "https://catalogiq-c4cr.onrender.com"}, clear=False):
        # Create pending request in DB
        db = SessionLocal()
        try:
            req = AccessRequest(
                request_id="REQ-PROD-TEST-001",
                name="Approval Requester",
                email=test_email,
                organization="Acme Render",
                role="Catalog Lead",
                status="PENDING",
                approval_token="valid_approval_token_123",
                activation_token=None,
                token_expires_at="2099-01-01T00:00:00",
                created_at="2026-09-14T00:00:00",
            )
            db.merge(req)
            db.commit()
        finally:
            db.close()

        with patch("backend.main.send_email") as mock_send:
            mock_send.return_value = {
                "success": True,
                "mode": "smtp",
                "recipient": test_email,
                "smtp_connection": "PASS",
                "smtp_authentication": "PASS",
                "message_accepted": "PASS",
                "error_type": None,
                "safe_error_message": None,
                "message": "Delivered"
            }
            res = client.get("/api/access-requests/REQ-PROD-TEST-001/approve?token=valid_approval_token_123")
            assert res.status_code == 200
            assert "Access Approved Successfully" in res.text
            assert mock_send.call_count == 2  # Requester email + Admin confirmation

            # Verify requester email has production activation link
            first_call_html = mock_send.call_args_list[0][1]["html"]
            assert "https://catalogiq-c4cr.onrender.com/activate.html" in first_call_html
            assert "localhost" not in first_call_html
