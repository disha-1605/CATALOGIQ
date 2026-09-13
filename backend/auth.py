"""Authentication and cryptographic security utilities for CatalogIQ."""

import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Tuple


def hash_password(password: str, salt: str = None) -> str:
    """Hash a password securely using PBKDF2-HMAC-SHA256 with a unique salt."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a PBKDF2-HMAC-SHA256 hash."""
    if not hashed_password or '$' not in hashed_password:
        return False
    try:
        salt, key_hex = hashed_password.split('$', 1)
        computed_key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return hmac.compare_digest(computed_key.hex(), key_hex)
    except Exception:
        return False


def generate_secure_token() -> str:
    """Generate a single-use cryptographically random URL-safe token."""
    return secrets.token_urlsafe(32)


def get_token_expiration(hours: int = 48) -> str:
    """Get ISO formatted expiration timestamp (default 48 hours)."""
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def is_token_expired(expires_at_iso: str) -> bool:
    """Check if an ISO timestamp has passed."""
    if not expires_at_iso:
        return True
    try:
        exp = datetime.fromisoformat(expires_at_iso)
        return datetime.utcnow() > exp
    except Exception:
        return True
