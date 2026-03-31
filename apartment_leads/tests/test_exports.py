"""Tests for the export module."""

import csv
import json
from pathlib import Path

import pytest

from src.exports.csv_export import export_csv, export_json, export_review_queue
from src.exports.database import LeadDatabase
from src.models import EnrichedField, ManagementStatus, PropertyLead


def make_lead(
    street: str = "123 Main St",
    city: str = "Oakland",
    status: ManagementStatus = ManagementStatus.LIKELY_OWNER_MANAGED,
    review: bool = False,
) -> PropertyLead:
    return PropertyLead(
        street_address=street,
        city=city,
        state="CA",
        zip_code="94601",
        county="Alameda",
        units_estimated=12,
        management_status=status,
        management_status_confidence=0.75,
        manual_review_flag=review,
        owner_name=EnrichedField(value="Jane Doe", source="test", confidence=0.7),
    )


class TestCsvExport:
    def test_creates_file(self, tmp_path):
        leads = [make_lead()]
        out = export_csv(leads, tmp_path / "leads.csv")
        assert out.exists()

    def test_correct_row_count(self, tmp_path):
        leads = [make_lead(street=f"{i} Main St") for i in range(5)]
        out = export_csv(leads, tmp_path / "leads.csv")
        with open(out, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 5

    def test_review_only_filter(self, tmp_path):
        leads = [
            make_lead(street="1 Main St", review=True),
            make_lead(street="2 Main St", review=False),
        ]
        out = export_csv(leads, tmp_path / "review.csv", review_only=True)
        with open(out, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 1

    def test_has_expected_columns(self, tmp_path):
        leads = [make_lead()]
        out = export_csv(leads, tmp_path / "leads.csv")
        with open(out, newline="") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
        assert "management_status" in cols
        assert "owner_name" in cols


class TestJsonExport:
    def test_creates_valid_json(self, tmp_path):
        leads = [make_lead()]
        out = export_json(leads, tmp_path / "leads.json")
        with open(out) as fh:
            data = json.load(fh)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["city"] == "Oakland"


class TestLeadDatabase:
    def test_upsert_and_query(self, tmp_path):
        db_path = tmp_path / "leads.db"
        db = LeadDatabase(db_path)
        leads = [
            make_lead(status=ManagementStatus.LIKELY_OWNER_MANAGED),
            make_lead(street="456 Oak Ave", status=ManagementStatus.LIKELY_THIRD_PARTY),
        ]
        db.upsert_leads(leads)
        owner_leads = list(db.query(management_status="likely_owner_managed"))
        assert len(owner_leads) == 1
        db.close()

    def test_count(self, tmp_path):
        db = LeadDatabase(tmp_path / "leads.db")
        leads = [make_lead(street=f"{i} St") for i in range(4)]
        db.upsert_leads(leads)
        assert db.count() == 4
        db.close()

    def test_upsert_is_idempotent(self, tmp_path):
        db = LeadDatabase(tmp_path / "leads.db")
        lead = make_lead()
        db.upsert_leads([lead])
        db.upsert_leads([lead])  # upsert same lead again
        assert db.count() == 1
        db.close()

    def test_roundtrip_preserves_fields(self, tmp_path):
        db = LeadDatabase(tmp_path / "leads.db")
        lead = make_lead()
        db.upsert_leads([lead])
        result = list(db.query())[0]
        assert result.city == "Oakland"
        assert result.management_status == ManagementStatus.LIKELY_OWNER_MANAGED
        assert result.owner_name is not None
        assert result.owner_name.value == "Jane Doe"
        db.close()
