"""Tests for core data models."""

import pytest
from src.models import (
    PropertyLead,
    SourceRecord,
    EnrichedField,
    ManagementStatus,
    ConfidenceLevel,
)


class TestPropertyLead:
    def test_full_address(self):
        lead = PropertyLead(
            street_address="123 Main St",
            city="Oakland",
            state="CA",
            zip_code="94601",
        )
        assert lead.full_address == "123 Main St, Oakland, CA, 94601"

    def test_full_address_missing_fields(self):
        lead = PropertyLead(street_address="123 Main St", city="Oakland")
        assert "123 Main St" in lead.full_address
        assert "Oakland" in lead.full_address

    def test_to_flat_dict_contains_required_keys(self):
        lead = PropertyLead(
            street_address="123 Main St",
            city="Oakland",
            state="CA",
            zip_code="94601",
        )
        d = lead.to_flat_dict()
        required = [
            "property_name", "street_address", "city", "state", "zip",
            "management_status", "management_status_confidence",
            "owner_name", "owner_entity", "source_urls", "manual_review_flag",
        ]
        for key in required:
            assert key in d, f"Missing key: {key}"

    def test_enriched_fields_in_flat_dict(self):
        from datetime import datetime
        lead = PropertyLead(
            street_address="123 Main St",
            city="Oakland",
            state="CA",
            zip_code="94601",
            owner_name=EnrichedField(
                value="John Smith",
                source="test",
                source_url="http://example.com",
                fetched_at=datetime.utcnow(),
                confidence=0.8,
            ),
        )
        d = lead.to_flat_dict()
        assert d["owner_name"] == "John Smith"
        assert d["owner_name_confidence"] == 0.8

    def test_management_status_defaults(self):
        lead = PropertyLead()
        assert lead.management_status == ManagementStatus.UNCLEAR
        assert lead.management_status_confidence == 0.0
        assert lead.management_status_confidence_level == ConfidenceLevel.LOW


class TestSourceRecord:
    def test_default_id_generated(self):
        r1 = SourceRecord()
        r2 = SourceRecord()
        assert r1.id != r2.id

    def test_optional_fields_default_none(self):
        r = SourceRecord()
        assert r.property_name is None
        assert r.apn is None
        assert r.owner_name_raw is None


class TestEnrichedField:
    def test_confidence_stored(self):
        ef = EnrichedField(value="Test LLC", source="ca_sos", confidence=0.75)
        assert ef.confidence == 0.75
        assert ef.value == "Test LLC"
