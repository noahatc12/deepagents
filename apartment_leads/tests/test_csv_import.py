"""Tests for the CSV import collector."""

import csv
import tempfile
from pathlib import Path

import pytest

from src.collectors.base import GeographyTarget
from src.collectors.csv_import import CsvImportCollector


TARGET = GeographyTarget(city="Oakland", state="CA")


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class TestCsvImportCollector:
    def test_reads_standard_columns(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        write_csv(
            [
                {
                    "property_name": "Oak Garden Apartments",
                    "street_address": "123 Main St",
                    "city": "Oakland",
                    "state": "CA",
                    "zip": "94601",
                    "county": "Alameda",
                    "units": "24",
                    "website": "https://oakgarden.example.com",
                    "phone": "510-555-1234",
                }
            ],
            csv_file,
        )
        collector = CsvImportCollector(csv_path=csv_file)
        records = list(collector.collect(TARGET))
        assert len(records) == 1
        rec = records[0]
        assert rec.property_name == "Oak Garden Apartments"
        assert rec.raw_address == "123 Main St"
        assert rec.units_raw == "24"

    def test_handles_missing_optional_columns(self, tmp_path):
        csv_file = tmp_path / "minimal.csv"
        write_csv(
            [{"street_address": "456 Oak Ave", "city": "Oakland", "state": "CA", "zip": "94601"}],
            csv_file,
        )
        collector = CsvImportCollector(csv_path=csv_file)
        records = list(collector.collect(TARGET))
        assert len(records) == 1
        assert records[0].property_name is None

    def test_missing_file_yields_no_records(self):
        collector = CsvImportCollector(csv_path=Path("/nonexistent/file.csv"))
        records = list(collector.collect(TARGET))
        assert records == []

    def test_is_always_available(self):
        collector = CsvImportCollector()
        assert collector.is_available(TARGET) is True

    def test_source_name(self):
        assert CsvImportCollector.source_name == "csv_import"
