"""
County Assessor Collector (stub + Alameda County example)

Many California counties expose parcel data as:
  - Downloadable CSV/GDB on their open data portals
  - Socrata / ArcGIS REST APIs (no auth required for read)

This module provides:
  1. A base AssessorCollector with the shared fetch/parse logic
  2. An AlamedaCountyAssessorCollector as a concrete example

To add a new county:
  - Subclass BaseAssessorCollector
  - Override source_name, BASE_URL, and _build_query()
  - Register in registry.py

Data source:
  Alameda County Assessor Open Data (Socrata)
  https://data.acgov.org/datasets/assessor-parcel-data
  Terms: Public domain / open data license.
  robots.txt: Checked at runtime.
"""

from __future__ import annotations

import json
from typing import Iterator, Optional
from urllib.parse import urlencode

from .base import BaseCollector, GeographyTarget
from ..models import SourceRecord
from ..utils.http import PoliteSession
from ..utils.rate_limiter import with_retry
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BaseAssessorCollector(BaseCollector):
    """
    Shared logic for Socrata-based county assessor open data portals.
    Subclasses set BASE_URL, DATASET_ID, and implement _build_where().
    """

    source_name = "assessor_base"
    BASE_URL: str = ""           # e.g. "https://data.acgov.org/resource"
    DATASET_ID: str = ""         # Socrata 4x4 ID
    PAGE_SIZE: int = 1000
    # Column name mapping: local_name -> column_name_in_dataset
    COLUMNS: dict[str, str] = {}

    # Property use codes that indicate multifamily / apartment
    # Override in subclass with jurisdiction-specific codes
    MULTIFAMILY_USE_CODES: set[str] = set()

    def _build_where(self, target: GeographyTarget) -> str:
        """
        Return a SoQL WHERE clause string to filter to target geography.
        Override in subclass.
        """
        raise NotImplementedError

    def _parse_row(self, row: dict) -> SourceRecord:
        """
        Map a raw Socrata row dict to a SourceRecord.
        Override in subclass for column differences.
        """
        raise NotImplementedError

    @with_retry(max_attempts=4, base_delay=2.0)
    def _fetch_page(self, url: str, params: dict) -> list[dict]:
        if not self._session:
            raise RuntimeError("No HTTP session configured")
        text = self._session.get(url, params=params)
        return json.loads(text)

    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        if not self.BASE_URL or not self.DATASET_ID:
            self._logger.warning(
                "%s: BASE_URL or DATASET_ID not configured", self.source_name
            )
            return

        endpoint = f"{self.BASE_URL}/{self.DATASET_ID}.json"
        offset = 0
        total = 0

        self._logger.info(
            "Fetching %s assessor data for %s", self.source_name, target.label
        )

        while True:
            params = {
                "$where": self._build_where(target),
                "$limit": self.PAGE_SIZE,
                "$offset": offset,
                "$order": ":id",
            }

            try:
                rows = self._fetch_page(endpoint, params)
            except Exception as exc:
                self._logger.error("Assessor fetch failed at offset %d: %s", offset, exc)
                break

            if not rows:
                break

            for row in rows:
                try:
                    yield self._parse_row(row)
                    total += 1
                except Exception as exc:
                    self._logger.debug("Row parse error: %s | row: %s", exc, row)

            if len(rows) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE

        self._logger.info("%s: yielded %d records", self.source_name, total)


class AlamedaCountyAssessorCollector(BaseAssessorCollector):
    """
    Fetches multifamily parcel data from Alameda County's open data portal.

    Source:
        Alameda County Open Data – Assessor Parcel File
        https://data.acgov.org/  (Socrata platform)
        License: Open Government License / public records

    TODO:
        - Confirm the exact dataset 4x4 ID once the portal is browsed
        - Map COLUMNS to actual column names in the dataset
        - Add MULTIFAMILY_USE_CODES from Alameda County use-code reference
    """

    source_name = "alameda_assessor"
    BASE_URL = "https://data.acgov.org/resource"
    DATASET_ID = "TODO_alameda_dataset_id"  # Replace with actual Socrata dataset ID

    # Map internal names -> actual Socrata column names (TODO: verify)
    COLUMNS = {
        "apn": "apn",
        "street_number": "situs_number",
        "street_name": "situs_street",
        "street_suffix": "situs_suffix",
        "city": "situs_city",
        "zip": "situs_zip",
        "owner_name": "owner_name",
        "owner_address": "owner_address",
        "use_code": "use_code",
        "units": "units",
        "year_built": "year_built",
    }

    # Alameda County use codes for multifamily residential
    # TODO: Confirm codes from county assessor documentation
    MULTIFAMILY_USE_CODES = {
        "1200",  # Example: Apartment (4+ units)
        "1201",
        "1202",
        "1203",
        "1204",
        "0300",  # Example: 2-4 unit
    }

    def _build_where(self, target: GeographyTarget) -> str:
        """Build SoQL WHERE for Alameda County."""
        conditions = []

        # Use-code filter for multifamily
        if self.MULTIFAMILY_USE_CODES:
            codes = ", ".join(f"'{c}'" for c in sorted(self.MULTIFAMILY_USE_CODES))
            conditions.append(f"{self.COLUMNS['use_code']} IN ({codes})")

        # Geography filter
        if target.city:
            conditions.append(
                f"upper({self.COLUMNS['city']}) = '{target.city.upper()}'"
            )
        elif target.zips:
            zip_list = ", ".join(f"'{z}'" for z in target.zips)
            conditions.append(f"{self.COLUMNS['zip']} IN ({zip_list})")
        elif target.county:
            # County-wide: no city filter needed since we're already in Alameda
            pass

        return " AND ".join(conditions) if conditions else "1=1"

    def _parse_row(self, row: dict) -> SourceRecord:
        c = self.COLUMNS
        number = row.get(c["street_number"], "").strip()
        name = row.get(c["street_name"], "").strip()
        suffix = row.get(c["street_suffix"], "").strip()
        street = " ".join(p for p in [number, name, suffix] if p)

        return SourceRecord(
            source_name=self.source_name,
            source_url=f"https://data.acgov.org/resource/{self.DATASET_ID}",
            raw_data=row,
            raw_address=street,
            raw_city=row.get(c["city"], ""),
            raw_state="CA",
            raw_zip=row.get(c["zip"], ""),
            raw_county="Alameda",
            apn=row.get(c["apn"]),
            units_raw=row.get(c["units"]),
            owner_name_raw=row.get(c["owner_name"]),
            mailing_address_raw=row.get(c["owner_address"]),
        )

    def is_available(self, target: GeographyTarget) -> bool:
        return (target.state or "").upper() in ("CA", "") and (
            (target.county or "").lower() in ("alameda", "alameda county", "")
            or any(z.startswith("946") for z in target.zips)
        )


class SacramentoCountyAssessorCollector(BaseAssessorCollector):
    """
    Stub for Sacramento County Assessor open data.

    Source:
        Sacramento County GIS Open Data
        https://data.saccounty.gov/  (Socrata platform)

    TODO:
        - Find the parcel dataset ID on data.saccounty.gov
        - Map column names
        - Add Sacramento use codes for multifamily
    """

    source_name = "sacramento_assessor"
    BASE_URL = "https://data.saccounty.gov/resource"
    DATASET_ID = "TODO_sacramento_dataset_id"

    COLUMNS = {
        "apn": "apn",
        "street_number": "street_number",
        "street_name": "street_name",
        "street_suffix": "street_type",
        "city": "city",
        "zip": "zip_code",
        "owner_name": "owner_name",
        "owner_address": "owner_mailing_address",
        "use_code": "use_code",
        "units": "units",
        "year_built": "year_built",
    }

    MULTIFAMILY_USE_CODES = {
        "TODO",  # Replace with Sacramento-specific codes
    }

    def _build_where(self, target: GeographyTarget) -> str:
        conditions = []
        if self.MULTIFAMILY_USE_CODES - {"TODO"}:
            codes = ", ".join(f"'{c}'" for c in sorted(self.MULTIFAMILY_USE_CODES))
            conditions.append(f"{self.COLUMNS['use_code']} IN ({codes})")
        if target.city:
            conditions.append(f"upper({self.COLUMNS['city']}) = '{target.city.upper()}'")
        elif target.zips:
            zip_list = ", ".join(f"'{z}'" for z in target.zips)
            conditions.append(f"{self.COLUMNS['zip']} IN ({zip_list})")
        return " AND ".join(conditions) if conditions else "1=1"

    def _parse_row(self, row: dict) -> SourceRecord:
        c = self.COLUMNS
        street = " ".join(
            p for p in [row.get(c["street_number"], ""), row.get(c["street_name"], ""),
                        row.get(c["street_suffix"], "")] if p
        ).strip()
        return SourceRecord(
            source_name=self.source_name,
            source_url=f"https://data.saccounty.gov/resource/{self.DATASET_ID}",
            raw_data=row,
            raw_address=street,
            raw_city=row.get(c["city"], ""),
            raw_state="CA",
            raw_zip=row.get(c["zip"], ""),
            raw_county="Sacramento",
            apn=row.get(c["apn"]),
            units_raw=row.get(c["units"]),
            owner_name_raw=row.get(c["owner_name"]),
            mailing_address_raw=row.get(c["owner_address"]),
        )

    def is_available(self, target: GeographyTarget) -> bool:
        return (target.county or "").lower() in ("sacramento", "sacramento county", "")
