"""Enterprise Email Service and Brand-Aligned HTML Templates for CatalogIQ.

Supports real SMTP delivery (Gmail, SendGrid, Amazon SES, Mailgun, Custom SMTP)
with TLS/SSL, explicit error diagnostics, and graceful development fallback.
"""

import os
import smtplib
import socket
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, Tuple
import httpx
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

logger = logging.getLogger("catalogiq.email")


def get_base_url() -> str:
    """Resolve the production application base URL dynamically."""
    explicit = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        return render_url
    if os.getenv("APP_ENV") == "production":
        return "https://catalogiq-c4cr.onrender.com"
    return "http://localhost:3000"


def get_api_base_url() -> str:
    """Resolve the production API base URL dynamically."""
    explicit = os.getenv("API_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    return get_base_url()


def get_admin_notification_email() -> str:
    """Resolve the admin notification email recipient."""
    return (os.getenv("ADMIN_NOTIFICATION_EMAIL") or "dishasengar1june@gmail.com").strip()


def _parse_sender(raw_from: str) -> Tuple[str, str]:
    """Extract (name, email) from 'Name <email@domain.com>' or 'email@domain.com'."""
    raw = (raw_from or "").strip()
    if "<" in raw and raw.endswith(">"):
        parts = raw.split("<", 1)
        name = parts[0].strip().strip("\"'") or "CatalogIQ Access Desk"
        email = parts[1].rstrip(">").strip()
        return name, email
    return "CatalogIQ Access Desk", raw or "dishasengar1june@gmail.com"


def get_email_config() -> Dict[str, Any]:
    """Dynamically read current email environment variables (Google Apps Script and SMTP)."""
    apps_script_url = os.getenv("GOOGLE_APPS_SCRIPT_URL", "").strip()
    apps_script_secret = os.getenv("GOOGLE_APPS_SCRIPT_SECRET", "").strip()

    host = os.getenv("SMTP_HOST", "").strip()
    port_str = os.getenv("SMTP_PORT", "587").strip()
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    user = (os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER") or "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes") or port == 465
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes") and not use_ssl

    admin_email = get_admin_notification_email()
    app_base_url = get_base_url()
    api_base_url = get_api_base_url()

    email_from = (os.getenv("EMAIL_FROM") or "dishasengar1june@gmail.com").strip()

    # Provider priority: Google Apps Script -> SMTP -> not_configured
    if apps_script_url:
        active_provider = "google_apps_script"
    elif host and user and password:
        active_provider = "smtp"
    else:
        active_provider = "not_configured"

    return {
        "active_provider": active_provider,
        "apps_script_url": apps_script_url,
        "apps_script_secret": apps_script_secret,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "email_from": email_from,
        "admin_email": admin_email,
        "app_base_url": app_base_url,
        "api_base_url": api_base_url,
    }


def get_smtp_config() -> Dict[str, Any]:
    """Dynamically read current SMTP/API environment variables (backwards compatibility)."""
    return get_email_config()


ADMIN_NOTIFICATION_EMAIL = get_admin_notification_email()
EMAIL_FROM = os.getenv("EMAIL_FROM", "CatalogIQ Access Desk <noreply@catalogiq.demo>")
APP_BASE_URL = get_base_url()
API_BASE_URL = get_api_base_url()


def is_smtp_configured() -> bool:
    """Check if real email credentials (Google Apps Script or SMTP) are provided in the environment."""
    cfg = get_email_config()
    return cfg["active_provider"] != "not_configured"


# =========================================================================
# GOOGLE APPS SCRIPT HTTPS TRANSPORT (Port 443 Relay)
# =========================================================================

def _send_via_google_apps_script(cfg: Dict[str, Any], to: str, subject: str, html: str, text: str) -> Dict[str, Any]:
    """Dispatch email via Google Apps Script HTTPS Web App (Port 443)."""
    url = cfg["apps_script_url"]
    secret = cfg["apps_script_secret"]

    payload = {
        "secret": secret,
        "to": to,
        "subject": subject,
        "html": html,
        "text": text,
    }
    headers = {
        "Content-Type": "application/json",
    }
    
    try:
        # follow_redirects=True is required because Google Apps Script doPost redirects (302) to echo URL
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.post(url, headers=headers, json=payload)
            
            if resp.status_code in (200, 201):
                try:
                    data = resp.json()
                except Exception:
                    data = {}

                if data.get("success") is True:
                    logger.info(f"Email successfully accepted by Google Apps Script for recipient: {to}")
                    return {
                        "success": True,
                        "mode": "google_apps_script",
                        "provider": "google_apps_script",
                        "recipient": to,
                        "smtp_connection": "PASS",
                        "smtp_authentication": "PASS",
                        "message_accepted": "PASS",
                        "error_type": None,
                        "safe_error_message": None,
                        "message": f"Email delivered to {to} via Google Apps Script (Gmail)",
                    }
                else:
                    err_msg = data.get("error") or data.get("message") or f"Apps Script rejected delivery (HTTP {resp.status_code})"
                    is_auth_err = "unauthorized" in err_msg.lower() or "secret" in err_msg.lower() or "auth" in err_msg.lower()
                    logger.error(f"Google Apps Script delivery error: {err_msg}")
                    return {
                        "success": False,
                        "mode": "google_apps_script_auth_error" if is_auth_err else "google_apps_script_error",
                        "provider": "google_apps_script",
                        "recipient": to,
                        "smtp_connection": "PASS",
                        "smtp_authentication": "FAIL" if is_auth_err else "PASS",
                        "message_accepted": "FAIL",
                        "error_type": "authentication_failure" if is_auth_err else "delivery_error",
                        "safe_error_message": "Google Apps Script rejected shared secret. Verify GOOGLE_APPS_SCRIPT_SECRET." if is_auth_err else f"Google Apps Script delivery failed: {err_msg}",
                        "message": f"Email delivery failed: {err_msg}",
                    }
            elif resp.status_code in (401, 403):
                logger.error(f"Google Apps Script unauthorized (HTTP {resp.status_code})")
                return {
                    "success": False,
                    "mode": "google_apps_script_auth_error",
                    "provider": "google_apps_script",
                    "recipient": to,
                    "smtp_connection": "PASS",
                    "smtp_authentication": "FAIL",
                    "message_accepted": "FAIL",
                    "error_type": "authentication_failure",
                    "safe_error_message": "Google Apps Script authentication failed. Verify GOOGLE_APPS_SCRIPT_SECRET.",
                    "message": "Email delivery failed: Google Apps Script authentication error.",
                }
            else:
                logger.error(f"Google Apps Script returned HTTP {resp.status_code}")
                return {
                    "success": False,
                    "mode": "google_apps_script_error",
                    "provider": "google_apps_script",
                    "recipient": to,
                    "smtp_connection": "PASS",
                    "smtp_authentication": "UNKNOWN",
                    "message_accepted": "FAIL",
                    "error_type": "transport_failure",
                    "safe_error_message": f"Google Apps Script returned HTTP {resp.status_code}.",
                    "message": f"Email delivery failed: Apps Script HTTP {resp.status_code}",
                }
    except (httpx.ConnectError, socket.gaierror) as conn_err:
        logger.error(f"Could not connect to Google Apps Script URL: {conn_err}")
        return {
            "success": False,
            "mode": "google_apps_script_conn_error",
            "provider": "google_apps_script",
            "recipient": to,
            "smtp_connection": "FAIL",
            "smtp_authentication": "SKIPPED",
            "message_accepted": "FAIL",
            "error_type": "connection_failure",
            "safe_error_message": "Could not connect to Google Apps Script Web App URL.",
            "message": "Email delivery failed: HTTPS connection error.",
        }
    except httpx.TimeoutException:
        logger.error("Google Apps Script request timed out")
        return {
            "success": False,
            "mode": "google_apps_script_timeout",
            "provider": "google_apps_script",
            "recipient": to,
            "smtp_connection": "FAIL",
            "smtp_authentication": "UNKNOWN",
            "message_accepted": "FAIL",
            "error_type": "timeout",
            "safe_error_message": "Google Apps Script Web App request timed out.",
            "message": "Email delivery failed: Request timeout.",
        }
    except Exception as exc:
        logger.error(f"Unexpected error in Google Apps Script delivery to {to}: {exc}")
        return {
            "success": False,
            "mode": "google_apps_script_error",
            "provider": "google_apps_script",
            "recipient": to,
            "smtp_connection": "UNKNOWN",
            "smtp_authentication": "UNKNOWN",
            "message_accepted": "FAIL",
            "error_type": "delivery_error",
            "safe_error_message": "An unexpected error occurred during Google Apps Script email delivery.",
            "message": "Email delivery failed due to a server error.",
        }


def _send_via_smtp(cfg: Dict[str, Any], to_clean: str, subject: str, html: str, text: str) -> Dict[str, Any]:
    """Dispatch email via direct SMTP with STARTTLS/SSL (local development fallback)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["email_from"]
    msg["To"] = to_clean

    part_text = MIMEText(text, "plain", "utf-8")
    part_html = MIMEText(html, "html", "utf-8")
    msg.attach(part_text)
    msg.attach(part_html)

    server = None
    try:
        if cfg["use_ssl"]:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
            server.ehlo()
            if cfg["use_tls"]:
                server.starttls()
                server.ehlo()

        # Authenticate
        server.login(cfg["user"], cfg["password"])
        
        # Send
        server.sendmail(cfg["email_from"], [to_clean], msg.as_string())
        server.quit()

        logger.info(f"Email successfully accepted by SMTP server for recipient: {to_clean}")
        return {
            "success": True,
            "mode": "smtp",
            "provider": "smtp",
            "recipient": to_clean,
            "smtp_connection": "PASS",
            "smtp_authentication": "PASS",
            "message_accepted": "PASS",
            "error_type": None,
            "safe_error_message": None,
            "message": f"Email delivered to {to_clean} via SMTP ({cfg['host']})",
        }

    except smtplib.SMTPAuthenticationError as auth_err:
        logger.error(f"SMTP authentication failed for user {cfg['user']}: {auth_err}")
        return {
            "success": False,
            "mode": "smtp_auth_error",
            "provider": "smtp",
            "recipient": to_clean,
            "smtp_connection": "PASS",
            "smtp_authentication": "FAIL",
            "message_accepted": "FAIL",
            "error_type": "authentication_failure",
            "safe_error_message": "SMTP authentication failed. Verify SMTP username and Google App Password.",
            "message": "Email delivery failed: SMTP authentication error.",
        }
    except (smtplib.SMTPConnectError, socket.timeout, ConnectionRefusedError, socket.gaierror) as conn_err:
        logger.error(f"SMTP connection failed to {cfg['host']}:{cfg['port']}: {conn_err}")
        return {
            "success": False,
            "mode": "smtp_conn_error",
            "provider": "smtp",
            "recipient": to_clean,
            "smtp_connection": "FAIL",
            "smtp_authentication": "SKIPPED",
            "message_accepted": "FAIL",
            "error_type": "connection_failure",
            "safe_error_message": f"Could not connect to SMTP server {cfg['host']}:{cfg['port']}.",
            "message": "Email delivery failed: SMTP connection error.",
        }
    except smtplib.SMTPRecipientsRefused as rec_err:
        logger.error(f"SMTP recipient refused for {to_clean}: {rec_err}")
        return {
            "success": False,
            "mode": "smtp_recipient_refused",
            "provider": "smtp",
            "recipient": to_clean,
            "smtp_connection": "PASS",
            "smtp_authentication": "PASS",
            "message_accepted": "FAIL",
            "error_type": "recipient_refused",
            "safe_error_message": f"Recipient address refused: {to_clean}.",
            "message": f"Email delivery failed: Recipient address refused ({to_clean}).",
        }
    except Exception as exc:
        logger.error(f"SMTP delivery error to {to_clean}: {exc}")
        return {
            "success": False,
            "mode": "smtp_error",
            "provider": "smtp",
            "recipient": to_clean,
            "smtp_connection": "UNKNOWN",
            "smtp_authentication": "UNKNOWN",
            "message_accepted": "FAIL",
            "error_type": "delivery_error",
            "safe_error_message": "An unexpected SMTP delivery error occurred.",
            "message": "Email delivery failed due to a server error.",
        }
    finally:
        if server:
            try:
                server.close()
            except Exception:
                pass


def send_email(to: str, subject: str, html: str, text: str) -> Dict[str, Any]:
    """
    Send an email using Google Apps Script HTTPS relay or fallback SMTP.
    Distinguishes honestly between accepted delivery, authentication failure,
    connection failure, and unconfigured dev fallback.
    Never exposes credentials, secrets, or passwords.
    """
    cfg = get_email_config()
    to_clean = (to or "").strip()
    provider = cfg["active_provider"]

    if provider == "google_apps_script":
        return _send_via_google_apps_script(cfg, to_clean, subject, html, text)
    elif provider == "smtp":
        return _send_via_smtp(cfg, to_clean, subject, html, text)
    else:
        # Development / Unconfigured Fallback Mode
        logger.info(f"[DEV EMAIL LOG] To: {to_clean} | Subject: {subject}")
        print("\n" + "=" * 70)
        print(f"📧 [CATALOGIQ DEV EMAIL LOG] To: {to_clean}")
        print(f"Subject: {subject}")
        print("-" * 70)
        print(text)
        print("=" * 70 + "\n")
        return {
            "success": False,
            "mode": "not_configured",
            "provider": "none",
            "recipient": to_clean,
            "smtp_connection": "SKIPPED",
            "smtp_authentication": "SKIPPED",
            "message_accepted": "SKIPPED",
            "error_type": "configuration_missing",
            "safe_error_message": "Email delivery is not configured. Set GOOGLE_APPS_SCRIPT_URL & GOOGLE_APPS_SCRIPT_SECRET (or SMTP) in environment.",
            "message": "Access request created, but email delivery is not configured.",
        }


# =========================================================================
# HTML EMAIL TEMPLATES (CatalogIQ Enterprise Design Language)
# =========================================================================

def _render_email_base(title: str, content_html: str) -> str:
    """Base responsive HTML email container matching CatalogIQ enterprise theme."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #FBF7F3;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #101827;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      background-color: #FBF7F3;
      padding: 32px 16px;
    }}
    .card {{
      max-width: 580px;
      margin: 0 auto;
      background-color: #FFFFFF;
      border-radius: 16px;
      border: 1px solid #E5E0DA;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(16, 24, 39, 0.04);
    }}
    .header {{
      background-color: #101827;
      padding: 24px 32px;
      border-bottom: 2px solid #E83E4F;
    }}
    .logo-badge {{
      display: inline-block;
      width: 32px;
      height: 32px;
      line-height: 32px;
      background-color: #E83E4F;
      color: #FFFFFF;
      font-weight: bold;
      font-size: 18px;
      text-align: center;
      border-radius: 8px;
      vertical-align: middle;
      margin-right: 12px;
    }}
    .brand-title {{
      color: #FFFFFF;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.02em;
      vertical-align: middle;
      display: inline-block;
    }}
    .brand-sub {{
      color: #94A3B8;
      font-size: 11px;
      font-family: monospace;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-top: 4px;
    }}
    .body {{
      padding: 32px;
    }}
    .tag {{
      display: inline-block;
      padding: 4px 10px;
      background-color: #FDE7E7;
      color: #9B1C1C;
      font-size: 11px;
      font-family: monospace;
      font-weight: 700;
      border-radius: 6px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 16px;
    }}
    .tag-approved {{
      background-color: #DEF7EC;
      color: #03543F;
    }}
    .tag-test {{
      background-color: #E0E7FF;
      color: #3730A3;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      color: #101827;
      margin: 0 0 12px 0;
      letter-spacing: -0.02em;
    }}
    p {{
      font-size: 14px;
      line-height: 1.6;
      color: #4B5563;
      margin: 0 0 16px 0;
    }}
    .data-table {{
      width: 100%;
      background-color: #FBF7F3;
      border: 1px solid #E5E0DA;
      border-radius: 12px;
      padding: 16px 20px;
      margin: 20px 0;
      box-sizing: border-box;
    }}
    .btn-primary {{
      display: inline-block;
      background-color: #E83E4F;
      color: #FFFFFF !important;
      text-decoration: none;
      font-weight: 600;
      font-size: 14px;
      padding: 12px 28px;
      border-radius: 10px;
      margin-top: 12px;
      text-align: center;
    }}
    .btn-secondary {{
      display: inline-block;
      background-color: #F3F4F6;
      color: #4B5563 !important;
      text-decoration: none;
      font-weight: 600;
      font-size: 13px;
      padding: 12px 20px;
      border-radius: 10px;
      margin-left: 8px;
      margin-top: 12px;
      text-align: center;
    }}
    .footer {{
      background-color: #F9FAFB;
      padding: 20px 32px;
      border-top: 1px solid #E5E7EB;
      text-align: center;
      font-size: 11px;
      font-family: monospace;
      color: #9CA3AF;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="card">
      <div class="header">
        <div>
          <span class="logo-badge">Q</span>
          <span class="brand-title">CatalogIQ</span>
        </div>
        <div class="brand-sub">Catalog intelligence for better search</div>
      </div>
      <div class="body">
        {content_html}
      </div>
      <div class="footer">
        CatalogIQ Enterprise Intelligence Platform · v1.0
      </div>
    </div>
  </div>
</body>
</html>"""


def build_admin_notification_email(
    name: str,
    email: str,
    organization: str,
    role: str,
    request_id: str,
    approval_url: str,
    reject_url: str,
    created_at_formatted: str
) -> Tuple[str, str]:
    """Generate HTML and plain text for new access request email to admin."""
    subject = "CatalogIQ — New Access Request"

    content_html = f"""
      <div class="tag">NEW ACCESS REQUEST</div>
      <h1>Access Request Pending Review</h1>
      <p>A new user has requested access to CatalogIQ.</p>
      
      <div class="data-table">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 6px 0; color: #6B7280; width: 35%;">Name:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right;">{name}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Email:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right; font-family: monospace;">{email}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Organization:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right;">{organization}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Role / Team:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right;">{role or 'Catalog Operations'}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Requested:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right; font-family: monospace;">{created_at_formatted}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Status:</td>
            <td style="padding: 6px 0; font-weight: 700; color: #E83E4F; text-align: right; font-family: monospace;">PENDING REVIEW</td>
          </tr>
        </table>
      </div>

      <div style="margin-top: 24px;">
        <a href="{approval_url}" class="btn-primary" style="color: #ffffff;">Grant Access</a>
        <a href="{reject_url}" class="btn-secondary">Review Request</a>
      </div>
      
      <p style="font-size: 12px; color: #9CA3AF; margin-top: 24px;">
        This single-use secure approval link expires in 48 hours. Request ID: {request_id}
      </p>
    """

    text = f"""CATALOGIQ
Catalog intelligence for better search

NEW ACCESS REQUEST

A new user has requested access to CatalogIQ.

Name: {name}
Email: {email}
Organization: {organization}
Role / Team: {role or 'Catalog Operations'}
Requested: {created_at_formatted}
Status: PENDING REVIEW

Primary CTA:
Grant Access
{approval_url}

Secondary CTA:
Review Request
{reject_url}

Request ID: {request_id}
"""

    return _render_email_base(subject, content_html), text


def build_requester_approved_email(
    name: str,
    organization: str,
    role: str,
    activation_url: str
) -> Tuple[str, str]:
    """Generate HTML and plain text for access-granted email to requester."""
    subject = "CatalogIQ — Your Access Has Been Approved"

    content_html = f"""
      <div class="tag tag-approved">ACCESS GRANTED</div>
      <h1>Welcome to CatalogIQ, {name}</h1>
      <p>Hi {name},</p>
      <p>Your request to access CatalogIQ has been approved.</p>
      
      <div class="data-table">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 6px 0; color: #6B7280; width: 35%;">Organization:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right;">{organization}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Role:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right;">{role or 'Catalog Operations'}</td>
          </tr>
        </table>
      </div>

      <p>Your account is now ready to activate.</p>

      <div style="margin: 28px 0;">
        <a href="{activation_url}" class="btn-primary" style="color: #ffffff;">Activate Your Account</a>
      </div>

      <div style="background-color: #FBF7F3; border: 1px solid #E5E0DA; border-radius: 10px; padding: 12px 16px; font-size: 12px; color: #6B7280;">
        <strong>Security Notice:</strong> This activation link is secure, single-use, and time-limited (expires in 48 hours).
      </div>
    """

    text = f"""CATALOGIQ
Catalog intelligence for better search

ACCESS GRANTED

Hi {name},

Your request to access CatalogIQ has been approved.

Organization: {organization}
Role: {role or 'Catalog Operations'}

Your account is now ready to activate.

Activate Your Account:
{activation_url}

This activation link is secure, single-use, and time-limited.
"""

    return _render_email_base(subject, content_html), text


def build_admin_approved_confirmation_email(
    name: str,
    email: str,
    organization: str,
    approved_at_formatted: str
) -> Tuple[str, str]:
    """Generate HTML and plain text for admin confirmation when an access request is approved."""
    subject = "CatalogIQ — Access Request Approved"

    content_html = f"""
      <div class="tag tag-approved">APPROVED</div>
      <h1>Access Request Confirmed</h1>
      <p>The following user's access has been successfully granted and an activation invitation has been dispatched.</p>

      <div class="data-table">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 6px 0; color: #6B7280; width: 35%;">Requester:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right;">{name}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Email:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right; font-family: monospace;">{email}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Organization:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right;">{organization}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Approved:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right; font-family: monospace;">{approved_at_formatted}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Approved by:</td>
            <td style="padding: 6px 0; font-weight: 700; color: #111827; text-align: right;">Disha</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Status:</td>
            <td style="padding: 6px 0; font-weight: 700; color: #03543F; text-align: right; font-family: monospace;">APPROVED</td>
          </tr>
        </table>
      </div>
    """

    text = f"""CATALOGIQ
Catalog intelligence for better search

ACCESS REQUEST APPROVED

Requester: {name}
Email: {email}
Organization: {organization}
Approved: {approved_at_formatted}
Approved by: Disha
Status: APPROVED
"""

    return _render_email_base(subject, content_html), text


def build_test_email(recipient: str, timestamp_formatted: str) -> Tuple[str, str]:
    """Generate HTML and plain text for safe admin delivery testing."""
    subject = "CatalogIQ — Email Delivery Test"

    content_html = f"""
      <div class="tag tag-test">EMAIL DELIVERY TEST</div>
      <h1>CatalogIQ Notification Service</h1>
      <p>This message confirms that the CatalogIQ notification service is configured correctly.</p>

      <div class="data-table">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 6px 0; color: #6B7280; width: 35%;">Recipient:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right; font-family: monospace;">{recipient}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Time:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #111827; text-align: right; font-family: monospace;">{timestamp_formatted}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #6B7280;">Status:</td>
            <td style="padding: 6px 0; font-weight: 700; color: #03543F; text-align: right; font-family: monospace;">ACTIVE</td>
          </tr>
        </table>
      </div>

      <p style="font-size: 13px; color: #6B7280;">All access requests, admin approvals, and activation invitations are routed through this service.</p>
    """

    text = f"""CATALOGIQ
Catalog intelligence for better search

Email delivery test

This message confirms that the CatalogIQ notification service is configured correctly.

Time: {timestamp_formatted}
Recipient: {recipient}
"""

    return _render_email_base(subject, content_html), text
