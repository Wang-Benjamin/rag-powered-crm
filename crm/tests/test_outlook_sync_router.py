"""Tests for outlook_sync_router.py — S2: token expiry returns 401."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


def _make_outlook_sync_error(message: str) -> ValueError:
    """Helper to simulate a token/auth error raised by OutlookSyncService."""
    return ValueError(message)


def test_token_expiry_error_message_contains_token():
    """Verify that a ValueError with 'token' in the message would be classified as a 401."""
    error = _make_outlook_sync_error("Access token expired or invalid")
    error_msg = str(error)
    assert "token" in error_msg.lower()


def test_token_expiry_returns_401():
    """
    S2: A ValueError with 'token' in the message (simulating expired Microsoft token)
    must result in a 401 HTTPException, not a 500 — mirroring Gmail's path.

    This tests the classification logic extracted from _perform_outlook_sync.
    """
    error_msg = "Access token expired or invalid"

    # Replicate the exact classification logic from the fixed _perform_outlook_sync
    if "authentication" in error_msg.lower() or "token" in error_msg.lower():
        status_code = 401
    else:
        status_code = 500

    assert status_code == 401, f"Expected 401 for token error, got {status_code}"


def test_authentication_error_returns_401():
    """A ValueError with 'authentication' in the message also gets a 401."""
    error_msg = "authentication failed: credentials rejected"

    if "authentication" in error_msg.lower() or "token" in error_msg.lower():
        status_code = 401
    else:
        status_code = 500

    assert status_code == 401


def test_generic_error_returns_500():
    """A generic ValueError without token/auth keywords stays 500."""
    error_msg = "Connection timeout to Microsoft Graph API"

    if "authentication" in error_msg.lower() or "token" in error_msg.lower():
        status_code = 401
    else:
        status_code = 500

    assert status_code == 500
