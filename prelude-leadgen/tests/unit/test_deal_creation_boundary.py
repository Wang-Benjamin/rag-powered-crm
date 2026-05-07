"""Static contract: lead conversion must not create deals."""

from pathlib import Path

LEADGEN_ROOT = Path(__file__).resolve().parents[2]


def test_lead_conversion_does_not_insert_deals_or_call_auto_deal_helper():
    source = (LEADGEN_ROOT / "crm_integration" / "integration_service.py").read_text()

    assert "INSERT INTO deals" not in source
    assert "_create_deals_per_hs_code" not in source
    assert '"deals_created": deals_created' in source
    assert "deals_created = 0" in source
