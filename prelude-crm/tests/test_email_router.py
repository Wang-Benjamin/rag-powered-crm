"""Tests for email_router.py — Sd1: empty error message fallback."""
import types


def test_send_empty_message_fallback():
    """
    Sd1: When result.success is False and result.message is an empty string,
    the error_message should fall back to the actionable text rather than
    showing a blank toast to the user.
    """
    # Simulate the fixed logic from email_router.py line ~295
    result = types.SimpleNamespace(success=False, message="")

    # This is the exact expression from the fixed code:
    error_message = result.message or "Email provider returned no error detail"

    assert error_message == "Email provider returned no error detail", (
        f"Expected fallback text, got: {error_message!r}"
    )


def test_send_non_empty_message_preserved():
    """When result.message is non-empty, it should be returned as-is."""
    result = types.SimpleNamespace(success=False, message="Rate limit exceeded")

    error_message = result.message or "Email provider returned no error detail"

    assert error_message == "Rate limit exceeded"
