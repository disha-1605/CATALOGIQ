"""Unit and integration tests for Google Apps Script production email delivery, diagnostics, and URL resolution."""

import os
import smtplib
import socket
from unittest.mock import patch, MagicMock
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.email_service import (
    send_email,
    get_base_url,
    get_api_base_url,
    get_admin_notification_email,
    get_email_config,
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


def test_email_configuration_missing_diagnostic():
    """Verify send_email returns structured not_configured when credentials and URLs are missing."""
    with patch.dict(os.environ, {
        "GOOGLE_APPS_SCRIPT_URL": "",
        "GOOGLE_APPS_SCRIPT_SECRET": "",
        "SMTP_HOST": "",
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
    }, clear=False):
        result = send_email("test@example.com", "Test Subject", "<p>HTML</p>", "Text")
        assert result["success"] is False
        assert result["mode"] == "not_configured"
        assert result["provider"] == "none"
        assert result["smtp_connection"] == "SKIPPED"
        assert result["smtp_authentication"] == "SKIPPED"
        assert result["message_accepted"] == "SKIPPED"
        assert result["error_type"] == "configuration_missing"
        assert "GOOGLE_APPS_SCRIPT_URL" in result["safe_error_message"]
        assert "secret" not in str(result).lower() or "secret" in result["safe_error_message"].lower()


# =========================================================================
# GOOGLE APPS SCRIPT HTTPS RELAY TESTS (Port 443)
# =========================================================================

def test_google_apps_script_delivery_success():
    """Verify send_email successfully dispatches via Google Apps Script HTTPS Web App."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "https://script.google.com/macros/s/AKfycbz_test_deployment_id/exec",
        "GOOGLE_APPS_SCRIPT_SECRET": "my_super_secret_shared_token_98765",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "message": "Email accepted by Gmail for recipient@company.demo"
        }
        
        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            result = send_email("recipient@company.demo", "Access Granted", "<p>Welcome</p>", "Welcome")
            assert result["success"] is True
            assert result["mode"] == "google_apps_script"
            assert result["provider"] == "google_apps_script"
            assert result["smtp_connection"] == "PASS"
            assert result["smtp_authentication"] == "PASS"
            assert result["message_accepted"] == "PASS"
            assert result["error_type"] is None
            assert mock_post.called
            
            call_url = mock_post.call_args[0][0]
            call_json = mock_post.call_args[1]["json"]
            assert call_url == "https://script.google.com/macros/s/AKfycbz_test_deployment_id/exec"
            assert call_json["secret"] == "my_super_secret_shared_token_98765"
            assert call_json["to"] == "recipient@company.demo"
            assert call_json["subject"] == "Access Granted"
            assert call_json["html"] == "<p>Welcome</p>"
            assert call_json["text"] == "Welcome"
            
            # Ensure the secret is NOT exposed in the returned result dictionary
            assert "my_super_secret_shared_token_98765" not in str(result)


def test_google_apps_script_http_401_auth_failure():
    """Verify send_email safely reports authentication failure when Apps Script rejects secret with HTTP 401."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "https://script.google.com/macros/s/AKfycbz_test_deployment_id/exec",
        "GOOGLE_APPS_SCRIPT_SECRET": "wrong_secret_token_123",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"success": False, "error": "Unauthorized: Invalid secret"}

        with patch("httpx.Client.post", return_value=mock_resp):
            result = send_email("recipient@company.demo", "Test", "<p>Hi</p>", "Hi")
            assert result["success"] is False
            assert result["mode"] == "google_apps_script_auth_error"
            assert result["provider"] == "google_apps_script"
            assert result["smtp_authentication"] == "FAIL"
            assert result["message_accepted"] == "FAIL"
            assert result["error_type"] == "authentication_failure"
            assert "GOOGLE_APPS_SCRIPT_SECRET" in result["safe_error_message"]
            assert "wrong_secret_token_123" not in str(result)


def test_google_apps_script_json_auth_failure_200():
    """Verify send_email handles Apps Script returning 200 with success=false unauthorized."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "https://script.google.com/macros/s/AKfycbz_test_deployment_id/exec",
        "GOOGLE_APPS_SCRIPT_SECRET": "bad_token",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": False, "error": "Unauthorized: Invalid secret"}

        with patch("httpx.Client.post", return_value=mock_resp):
            result = send_email("recipient@company.demo", "Test", "<p>Hi</p>", "Hi")
            assert result["success"] is False
            assert result["mode"] == "google_apps_script_auth_error"
            assert result["smtp_authentication"] == "FAIL"
            assert result["message_accepted"] == "FAIL"
            assert result["error_type"] == "authentication_failure"
            assert "bad_token" not in str(result)


def test_google_apps_script_http_500_transport_failure():
    """Verify send_email safely reports transport failure when Apps Script throws internal exception."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "https://script.google.com/macros/s/AKfycbz_test_deployment_id/exec",
        "GOOGLE_APPS_SCRIPT_SECRET": "valid_secret",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"success": False, "error": "Internal Apps Script error"}

        with patch("httpx.Client.post", return_value=mock_resp):
            result = send_email("recipient@company.demo", "Test", "<p>Hi</p>", "Hi")
            assert result["success"] is False
            assert result["mode"] == "google_apps_script_error"
            assert result["provider"] == "google_apps_script"
            assert result["message_accepted"] == "FAIL"
            assert result["error_type"] == "transport_failure"
            assert "HTTP 500" in result["safe_error_message"]


def test_google_apps_script_connection_error_diagnostic():
    """Verify send_email safely reports connection error when Apps Script endpoint is unreachable."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "https://unreachable.script.google.com/macros/s/exec",
        "GOOGLE_APPS_SCRIPT_SECRET": "valid_secret",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
            result = send_email("recipient@company.demo", "Test", "<p>Hi</p>", "Hi")
            assert result["success"] is False
            assert result["mode"] == "google_apps_script_conn_error"
            assert result["provider"] == "google_apps_script"
            assert result["smtp_connection"] == "FAIL"
            assert result["error_type"] == "connection_failure"
            assert "Could not connect" in result["safe_error_message"]


def test_google_apps_script_timeout_diagnostic():
    """Verify send_email safely reports timeout when Apps Script request exceeds timeout limit."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "https://script.google.com/macros/s/exec",
        "GOOGLE_APPS_SCRIPT_SECRET": "valid_secret",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
            result = send_email("recipient@company.demo", "Test", "<p>Hi</p>", "Hi")
            assert result["success"] is False
            assert result["mode"] == "google_apps_script_timeout"
            assert result["provider"] == "google_apps_script"
            assert result["error_type"] == "timeout"
            assert "timed out" in result["safe_error_message"].lower()


# =========================================================================
# SMTP FALLBACK TESTS (Local Development)
# =========================================================================

def test_smtp_connection_failure_diagnostic():
    """Verify send_email reports connection failure safely when server is unreachable."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "",
        "GOOGLE_APPS_SCRIPT_SECRET": "",
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
            assert "dummy_password" not in str(result)


def test_smtp_authentication_failure_diagnostic():
    """Verify send_email reports authentication failure safely when credentials rejected."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "",
        "GOOGLE_APPS_SCRIPT_SECRET": "",
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
            assert "wrong_password" not in str(result)


def test_smtp_message_accepted():
    """Verify send_email reports PASS on all checks when SMTP accepts message."""
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "",
        "GOOGLE_APPS_SCRIPT_SECRET": "",
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
    env_vars = {
        "GOOGLE_APPS_SCRIPT_URL": "https://script.google.com/macros/s/test/exec",
        "GOOGLE_APPS_SCRIPT_SECRET": "top_secret_token_val",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        res = client.get("/api/admin/email-config-status")
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "google_apps_script"
        assert data["configured"] is True
        assert data["apps_script_url_configured"] is True
        assert data["secret_configured"] is True
        assert data["google_apps_script_configured"] is True
        assert "smtp_host_configured" in data
        assert "admin_notification_email_configured" in data
        assert "admin_notification_email" in data
        assert "app_base_url" in data
        assert "api_base_url" in data
        # Ensure secret is NEVER present
        assert "top_secret_token_val" not in str(data)
        assert "secret" not in data or isinstance(data.get("secret_configured"), bool)


def test_admin_test_email_endpoint_mocked():
    """Verify POST and GET /api/admin/test-email return safe diagnostic result."""
    with patch("backend.main.send_email") as mock_send:
        mock_send.return_value = {
            "success": True,
            "mode": "google_apps_script",
            "provider": "google_apps_script",
            "recipient": "dishasengar1june@gmail.com",
            "smtp_connection": "PASS",
            "smtp_authentication": "PASS",
            "message_accepted": "PASS",
            "error_type": None,
            "safe_error_message": None,
            "message": "Email delivered to dishasengar1june@gmail.com via Google Apps Script (Gmail)"
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
                "mode": "google_apps_script",
                "provider": "google_apps_script",
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
                "mode": "google_apps_script",
                "provider": "google_apps_script",
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

