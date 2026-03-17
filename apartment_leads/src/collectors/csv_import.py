"""
CSV Import Collector

Reads a user-supplied CSV file of properties and emits SourceRecord objects.
This is the lowest-friction way to inject your own property list.

Expected CSV columns (all optional except at least one address field):
    property_name, street_address, city, state, zip, county,
    units, apn, website, phone, owner_name, owner_entity,
    mailing_address, management_name, notes
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Optional

from .base import BaseCollector, GeographyTarget
from ..models import SourceRecord


class CsvImportCollector(BaseCollector):
    """
    Collector that reads properties from a user-supplied CSV file.

    Config keys:
        csv_path (str, required): Path to the input CSV file.
        delimiter (str, default ","): CSV delimiter.
    """

    source_name = "csv_import"

    def __init__(self, csv_path: Optional[Path] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        path_from_config = self._config.get("csv_path")
        self._csv_path = csv_path or (Path(path_from_config) if path_from_config else None)

    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        if not self._csv_path or not self._csv_path.exists():
            self._logger.warning(
                "CSV import path not set or does not exist: %s", self._csv_path
            )
            return

        delimiter = self._config.get("delimiter", ",")
        self._logger.info("Reading CSV: %s", self._csv_path)

        with open(self._csv_path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, delimiter=delimiter)
            for i, row in enumerate(reader):
                row = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items()}
                record = SourceRecord(
                    source_name=self.source_name,
                    source_url=f"file://{self._csv_path.resolve()}",
                    raw_data=dict(row),
                    raw_address=row.get("street_address", row.get("address", "")),
                    raw_city=row.get("city", ""),
                    raw_state=row.get("state", ""),
                    raw_zip=row.get("zip", row.get("zip_code", "")),
                    raw_county=row.get("county", ""),
                    property_name=row.get("property_name") or None,
                    units_raw=row.get("units", row.get("unit_count", "")) or None,
                    owner_name_raw=row.get("owner_name") or None,
                    owner_entity_raw=row.get("owner_entity") or None,
                    mailing_address_raw=row.get("mailing_address") or None,
                    website_raw=row.get("website") or None,
                    phone_raw=row.get("phone") or None,
                    management_name_raw=row.get("management_name") or None,
                    apn=row.get("apn") or None,
                )
                yield record

        self._logger.info("CSV import complete: %s rows read", i + 1)
