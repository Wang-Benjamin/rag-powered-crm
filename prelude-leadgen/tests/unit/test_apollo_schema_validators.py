from __future__ import annotations

import pytest

from apollo_io.schemas import (
    ApolloEnrichedLead,
    ApolloEnrichmentRequest,
    ApolloLead,
    ApolloPreviewLead,
    ApolloSearchRequest,
)


def test_apollo_search_request_limits_keywords_and_job_titles() -> None:
    ApolloSearchRequest(industry="Lighting", location="USA", keywords=["a"] * 5, job_titles=["t"] * 10)

    with pytest.raises(ValueError):
        ApolloSearchRequest(industry="Lighting", location="USA", keywords=["a"] * 6)

    with pytest.raises(ValueError):
        ApolloSearchRequest(industry="Lighting", location="USA", job_titles=["t"] * 11)


def test_apollo_lead_normalizes_invalid_email_and_website() -> None:
    lead = ApolloLead(company_name="Acme", contact_email="not-an-email", website="acme.com")
    assert lead.contact_email is None
    assert lead.website == "https://acme.com"


def test_apollo_preview_and_enriched_leads_keep_field_normalization() -> None:
    preview = ApolloPreviewLead(company_name="Acme", website="example.com")
    assert preview.website == "https://example.com"

    enriched = ApolloEnrichedLead(company_name="Acme", contact_email="broken-email")
    assert enriched.contact_email is None


def test_apollo_enrichment_request_requires_reasonable_company_id_counts() -> None:
    ApolloEnrichmentRequest(company_ids=["1"])

    with pytest.raises(ValueError):
        ApolloEnrichmentRequest(company_ids=[])

    with pytest.raises(ValueError):
        ApolloEnrichmentRequest(company_ids=[str(i) for i in range(101)])
