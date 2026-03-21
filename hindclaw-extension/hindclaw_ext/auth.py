"""Shared JWT parsing for hindclaw extensions.

Used by both HindclawTenant (core API auth) and HindclawHttp (/ext/ route auth).
Reads HINDCLAW_JWT_SECRET from os.environ on each call (not at import time —
the env var may not be set yet when the module is first imported by the extension loader).
"""
import os

import jwt


def _get_jwt_secret() -> str:
    """Read JWT secret from environment.

    Called per-decode, not at import time. The env var may not be set yet
    when the module is first imported by the extension loader.

    Returns:
        The JWT secret string.

    Raises:
        RuntimeError: If HINDCLAW_JWT_SECRET is not set or empty.
    """
    secret = os.environ.get("HINDCLAW_JWT_SECRET", "")
    if not secret:
        raise RuntimeError("HINDCLAW_JWT_SECRET environment variable is not set")
    return secret


def decode_jwt(token: str) -> dict:
    """Decode and validate a hindclaw JWT.

    Args:
        token: Raw JWT string (without "Bearer " prefix).

    Returns:
        Decoded claims dictionary.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is malformed or signature is invalid.
        RuntimeError: If HINDCLAW_JWT_SECRET is not set.
    """
    return jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
