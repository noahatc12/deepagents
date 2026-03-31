"""Tests for the management classifier."""

import pytest
from src.classifiers.management import ManagementClassifier, classify_leads
from src.models import (
    EnrichedField,
    ManagementStatus,
    PropertyLead,
)
from datetime import datetime


def ef(value: str, confidence: float = 0.7) -> EnrichedField:
    return EnrichedField(value=value, source="test", confidence=confidence)


class TestManagementClassifier:
    def setup_method(self):
        self.clf = ManagementClassifier(unclear_threshold=0.2)

    def test_known_pm_company_classified_third_party(self):
        lead = PropertyLead(
            street_address="100 Main St",
            city="Oakland",
            state="CA",
            zip_code="94601",
            owner_entity=ef("Greystar Real Estate LLC"),
        )
        result = self.clf.classify(lead)
        assert result.status == ManagementStatus.LIKELY_THIRD_PARTY

    def test_self_managed_text_classified_owner_managed(self):
        lead = PropertyLead(
            street_address="200 Oak Ave",
            city="Oakland",
            state="CA",
            zip_code="94601",
            property_name="Self-Managed Apartments",
        )
        result = self.clf.classify(lead)
        assert result.status == ManagementStatus.LIKELY_OWNER_MANAGED

    def test_individual_name_suggests_owner_managed(self):
        lead = PropertyLead(
            street_address="300 Pine St",
            city="Oakland",
            state="CA",
            zip_code="94601",
            owner_name=ef("John Smith"),
        )
        result = self.clf.classify(lead)
        # Individual name = some owner-managed signal
        assert result.signals_fired  # at least one signal

    def test_pm_website_domain_classified_third_party(self):
        lead = PropertyLead(
            street_address="400 Elm St",
            city="Oakland",
            state="CA",
            zip_code="94601",
            website="https://www.greystar.com/properties/some-apartment",
        )
        result = self.clf.classify(lead)
        assert result.status == ManagementStatus.LIKELY_THIRD_PARTY
        assert result.detected_company

    def test_no_info_leans_owner_managed(self):
        lead = PropertyLead(
            street_address="500 Cedar Blvd",
            city="Oakland",
            state="CA",
            zip_code="94601",
        )
        result = self.clf.classify(lead)
        # No management name = fires "no_management_field" signal (-0.3),
        # which exceeds the unclear threshold (0.2), so classified as likely_owner_managed.
        # Absence of PM branding is itself a weak owner-managed indicator.
        assert result.status == ManagementStatus.LIKELY_OWNER_MANAGED
        assert "no_management_field" in result.signals_fired

    def test_confidence_is_bounded(self):
        lead = PropertyLead(
            street_address="600 Walnut Dr",
            city="Oakland",
            state="CA",
            zip_code="94601",
            owner_entity=ef("Greystar Real Estate Partners LLC"),
            website="https://www.greystar.com/properties/test",
        )
        result = self.clf.classify(lead)
        assert 0.0 <= result.confidence <= 1.0


class TestClassifyLeads:
    def test_bulk_classify(self):
        leads = [
            PropertyLead(street_address=f"{i} Main St", city="Oakland", state="CA", zip_code="94601")
            for i in range(5)
        ]
        classified = classify_leads(leads)
        assert len(classified) == 5
        for lead in classified:
            assert lead.management_status is not None

    def test_review_flag_set_for_unclear(self):
        lead = PropertyLead(
            street_address="999 Unknown Rd",
            city="Oakland",
            state="CA",
            zip_code="94601",
        )
        classified = classify_leads([lead])
        # No signals = unclear = should be flagged for review
        assert classified[0].manual_review_flag is True
