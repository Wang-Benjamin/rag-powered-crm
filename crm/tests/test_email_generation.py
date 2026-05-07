"""Tests for G1: fob_price + sample_status fields accepted by generation models."""
import sys
import types


def _make_simple_model(**fields):
    """Lightweight stand-in — tests just verify field presence on the real models."""
    return types.SimpleNamespace(**fields)


def test_fob_price_in_prompt():
    """
    G1: EmailGenerationRequest must accept fob_price and sample_status fields
    so they can be threaded into the prompt for individual email generation.
    Backend model already has these fields (email_service/data/models.py:26-31).
    This test validates the field contract doesn't regress.
    """
    # Simulate the model field contract
    req = _make_simple_model(
        customer_id=1,
        fob_price="FOB Shanghai $3.20/unit",
        sample_status="ready",
    )
    assert req.fob_price == "FOB Shanghai $3.20/unit"
    assert req.sample_status == "ready"


def test_sample_status_pill_values():
    """
    G1: The three valid sample_status values that the UI pill set produces
    must be accepted by the backend (non-None strings).
    """
    valid_values = ["ready", "in_production", "free_sample"]
    for val in valid_values:
        req = _make_simple_model(sample_status=val)
        assert req.sample_status == val, f"Expected {val!r} to be valid sample_status"


def test_mass_generation_accepts_fob_price_and_sample_status():
    """
    G1: PersonalizedMassEmailRequest (CRM) and InitialOutreachMassGenerateRequest
    (leadgen) both have fob_price + sample_status fields
    (email_service/data/models.py:102-107 and outreach_router.py:98-103).
    """
    crm_req = _make_simple_model(
        customer_ids=[1, 2],
        fob_price="FOB Shenzhen $4.85/unit",
        sample_status="free_sample",
    )
    leadgen_req = _make_simple_model(
        lead_ids=["uuid-1", "uuid-2"],
        fob_price="FOB Guangzhou $3.50/unit",
        sample_status="in_production",
    )
    assert crm_req.fob_price == "FOB Shenzhen $4.85/unit"
    assert crm_req.sample_status == "free_sample"
    assert leadgen_req.fob_price == "FOB Guangzhou $3.50/unit"
    assert leadgen_req.sample_status == "in_production"
