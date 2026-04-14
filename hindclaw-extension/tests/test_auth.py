"""Tests for hindclaw_ext.auth — shared JWT parsing."""

import time

import jwt as pyjwt
import pytest

from hindclaw_ext.auth import decode_jwt

TEST_SECRET = "test-secret-key-for-auth-tests!!"


def _make_jwt(claims: dict, secret: str = TEST_SECRET) -> str:
    return pyjwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch):
    """Ensure tests use test secret, not any real HINDCLAW_JWT_SECRET on this host."""
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", TEST_SECRET)


def test_decode_valid_jwt():
    token = _make_jwt(
        {
            "client_id": "app-prod",
            "sender": "telegram:100001",
            "agent": "agent-alpha",
            "exp": int(time.time()) + 300,
        }
    )
    claims = decode_jwt(token)
    assert claims["client_id"] == "app-prod"
    assert claims["sender"] == "telegram:100001"


def test_decode_expired_jwt():
    token = _make_jwt({"exp": int(time.time()) - 10})
    with pytest.raises(Exception, match="expired"):
        decode_jwt(token)


@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
def test_decode_wrong_secret():
    token = _make_jwt({"exp": int(time.time()) + 300}, secret="wrong")
    with pytest.raises(Exception, match="Signature verification failed"):
        decode_jwt(token)


def test_decode_garbage():
    with pytest.raises(Exception):
        decode_jwt("not-a-jwt")


def test_decode_missing_secret(monkeypatch):
    """RuntimeError if HINDCLAW_JWT_SECRET is not set."""
    monkeypatch.delenv("HINDCLAW_JWT_SECRET")
    with pytest.raises(RuntimeError, match="not set"):
        decode_jwt(_make_jwt({"exp": int(time.time()) + 300}))
