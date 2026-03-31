"""Tests for the normalization pipeline."""

import pytest
from datetime import datetime

from src.models import SourceRecord
from src.normalizers.pipeline import NormalizationPipeline


def make_record(**kwargs) -> SourceRecord:
    defaults = {
        "source_name": "test",
        "source_url": "http://example.com",
        "raw_address": "123 Main Street",
        "raw_city": "Oakland",
        "raw_state": "CA",
        "raw_zip": "94601",
        "raw_county": "Alameda",
    }
    defaults.update(kwargs)
    return SourceRecord(**defaults)


class TestNormalizationPipeline:
    def setup_method(self):
        self.pipe = NormalizationPipeline()

    def test_single_record_yields_single_lead(self):
        records = [make_record()]
        leads = self.pipe.run(records)
        assert len(leads) == 1

    def test_deduplication_same_address(self):
        records = [
            make_record(source_name="assessor"),
            make_record(source_name="csv_import"),
        ]
        leads = self.pipe.run(records)
        assert len(leads) == 1

    def test_deduplication_different_addresses(self):
        records = [
            make_record(raw_address="123 Main St"),
            make_record(raw_address="456 Oak Ave"),
        ]
        leads = self.pipe.run(records)
        assert len(leads) == 2

    def test_merges_source_names(self):
        records = [
            make_record(source_name="assessor"),
            make_record(source_name="csv_import"),
        ]
        leads = self.pipe.run(records)
        assert "assessor" in leads[0].source_names
        assert "csv_import" in leads[0].source_names

    def test_skips_records_with_no_address(self):
        records = [
            make_record(raw_address="", raw_city="", raw_state="", raw_zip=""),
            make_record(raw_address="123 Main St"),
        ]
        leads = self.pipe.run(records)
        # Only the record with an address should survive
        assert len(leads) == 1

    def test_units_parsed_from_raw(self):
        records = [make_record(units_raw="12 units")]
        leads = self.pipe.run(records)
        assert leads[0].units_estimated == 12

    def test_state_normalized_to_uppercase(self):
        records = [make_record(raw_state="california")]
        leads = self.pipe.run(records)
        assert leads[0].state == "CA"

    def test_owner_name_carried_through(self):
        from src.models import EnrichedField
        records = [make_record(owner_name_raw="John Smith Properties")]
        leads = self.pipe.run(records)
        assert leads[0].owner_name is not None
        assert "john smith properties" in (leads[0].owner_name.value or "").lower()
