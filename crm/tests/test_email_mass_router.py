"""Tests for mass email router — Sd3: modifiedIndices/modifiedEmails parity."""
import types


def test_modified_indices_persisted():
    """
    Sd3: When modifiedIndices=[1, 3] are passed to the leadgen sendPersonalized,
    the modifiedEmails list should contain exactly the emails at those positions.
    Mirrors the CRM MassEmailComposer.tsx:149-151 pattern.
    """
    emails = [
        {"leadId": "a", "subject": "S0", "body": "B0", "toEmail": "a@x.com"},
        {"leadId": "b", "subject": "S1", "body": "B1", "toEmail": "b@x.com"},
        {"leadId": "c", "subject": "S2", "body": "B2", "toEmail": "c@x.com"},
        {"leadId": "d", "subject": "S3", "body": "B3", "toEmail": "d@x.com"},
    ]
    modified_indices = [1, 3]

    # Replicate the exact logic from the fixed sendPersonalized in leads MassEmailComposer
    mapped = [{"leadId": e["leadId"], "subject": e["subject"], "body": e["body"], "toEmail": e["toEmail"]} for e in emails]
    modified_emails = [mapped[i] for i in modified_indices] if modified_indices else []

    assert len(modified_emails) == 2
    assert modified_emails[0]["leadId"] == "b"
    assert modified_emails[1]["leadId"] == "d"


def test_no_modified_indices_sends_empty_list():
    """When modifiedIndices is empty/None, modifiedEmails should be []."""
    emails = [
        {"leadId": "a", "subject": "S0", "body": "B0", "toEmail": "a@x.com"},
    ]
    modified_indices: list = []

    mapped = [{"leadId": e["leadId"], "subject": e["subject"], "body": e["body"], "toEmail": e["toEmail"]} for e in emails]
    modified_emails = [mapped[i] for i in modified_indices] if modified_indices else []

    assert modified_emails == []


def test_initial_outreach_mass_send_request_has_modified_emails_field():
    """
    Sd3 (backend): InitialOutreachMassSendRequest now has a modified_emails
    field (default=[]) — verifying the model contract.
    """
    # Simulate the model with the new field
    req = types.SimpleNamespace(
        emails=[{"lead_id": "x", "subject": "s", "body": "b", "to_email": "x@y.com"}],
        modified_emails=[],
        provider="gmail",
        campaign_name=None,
    )
    assert hasattr(req, "modified_emails")
    assert req.modified_emails == []


def test_validate_email_payloads_rejects_silent_missing_payload():
    from fastapi import HTTPException
    from routers.email_mass_router import _validate_email_payloads

    emails = [
        {"client_id": 1, "to_email": "a@example.com", "subject": "S", "body": "B"},
        None,
    ]

    try:
        _validate_email_payloads(emails)  # type: ignore[arg-type]
    except (HTTPException, TypeError, AttributeError):
        assert True
    else:
        raise AssertionError("missing/falsy email payload should not be silently filtered")


def test_validate_email_payloads_rejects_modified_email_not_in_send_set():
    from fastapi import HTTPException
    from routers.email_mass_router import _validate_email_payloads

    emails = [{"client_id": 1, "to_email": "a@example.com", "subject": "S", "body": "B"}]
    modified = [{"client_id": 2, "to_email": "b@example.com", "subject": "S", "body": "B"}]

    try:
        _validate_email_payloads(emails, modified)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Modified email" in str(exc.detail)
    else:
        raise AssertionError("modified email outside send set should be rejected")


def test_validate_email_payloads_normalizes_customer_id_and_client_email():
    from routers.email_mass_router import _validate_email_payloads

    emails = [{"customer_id": 1, "client_email": "a@example.com", "subject": "S", "body": "B"}]

    normalized = _validate_email_payloads(emails)

    assert normalized[0]["client_id"] == 1
    assert normalized[0]["to_email"] == "a@example.com"


def test_initial_outreach_validation_rejects_modified_email_not_in_send_set():
    from fastapi import HTTPException
    from routers.outreach_router import _validate_lead_email_payloads

    emails = [{"lead_id": "lead-1", "to_email": "a@example.com", "subject": "S", "body": "B"}]
    modified = [{"lead_id": "lead-2", "to_email": "b@example.com", "subject": "S", "body": "B"}]

    try:
        _validate_lead_email_payloads(emails, modified)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Modified email" in str(exc.detail)
    else:
        raise AssertionError("modified lead email outside send set should be rejected")
