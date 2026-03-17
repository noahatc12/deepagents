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
from typing import Iterator

from .base import BaseCollector, GeographyTarget
from ..models import SourceRecord
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


class AlamedaCountyArcGISAssessorCollector(BaseCollector):
    """
    Fetches multifamily parcel data from Alameda County's open data portal.

    Source:
        Alameda County Open Data Hub (ArcGIS Hub)
        Parcels dataset: https://data.acgov.org/datasets/2b026350b5dd40b18ed7a321fdcdba81_0
        License: Open Government License / public records

    The county switched from Socrata to ArcGIS Hub. This collector uses the
    ArcGIS Feature Service query API for paginated access.
    """

    source_name = "alameda_assessor"

    # ArcGIS Hub dataset GUID for Alameda County Parcels
    # https://data.acgov.org/datasets/2b026350b5dd40b18ed7a321fdcdba81_0
    ITEM_GUID = "2b026350b5dd40b18ed7a321fdcdba81"
    LAYER_INDEX = 0
    PAGE_SIZE = 1000

    # ArcGIS Hub provides a standard FeatureServer query endpoint for each dataset
    @property
    def _query_url(self) -> str:
        return (
            f"https://data.acgov.org/datasets/{self.ITEM_GUID}_{self.LAYER_INDEX}"
            f"/FeatureServer/query"
        )

    # Alameda County parcel field names (ArcGIS hosted layer)
    COLUMNS = {
        "apn": "APN",
        "street_number": "SITUS_NUMBER",
        "street_name": "SITUS_STREET",
        "street_suffix": "SITUS_SUFFIX",
        "city": "SITUS_CITY",
        "zip": "SITUS_ZIP",
        "owner_name": "OWNER_NAME",
        "owner_address": "OWNER_ADDRESS",
        "use_code": "USE_CODE",
        "units": "UNITS",
        "year_built": "YEAR_BUILT",
    }

    # Alameda County multifamily use codes (California standard range)
    MULTIFAMILY_USE_CODES = {
        "1220",  # Two-family dwellings (duplexes)
        "1230",  # Three- to four-family dwellings
        "1240",  # Five-to-12-unit apartments
        "1250",  # 13+ unit apartments
        "1260",  # Mobile home parks
    }

    def _build_where(self, target: GeographyTarget) -> str:
        conditions = []

        if self.MULTIFAMILY_USE_CODES:
            codes = ", ".join(f"'{c}'" for c in sorted(self.MULTIFAMILY_USE_CODES))
            conditions.append(f"{self.COLUMNS['use_code']} IN ({codes})")

        if target.city:
            conditions.append(
                f"UPPER({self.COLUMNS['city']}) = '{target.city.upper()}'"
            )
        elif target.zips:
            zip_list = ", ".join(f"'{z}'" for z in target.zips)
            conditions.append(f"{self.COLUMNS['zip']} IN ({zip_list})")

        return " AND ".join(conditions) if conditions else "1=1"

    @with_retry(max_attempts=4, base_delay=2.0)
    def _fetch_page(self, where: str, offset: int) -> list[dict]:
        if not self._session:
            raise RuntimeError("No HTTP session configured")
        params = {
            "where": where,
            "outFields": ",".join(self.COLUMNS.values()),
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": self.PAGE_SIZE,
            "f": "json",
        }
        text = self._session.get(self._query_url, params=params)
        data = json.loads(text)
        # ArcGIS returns {"features": [{"attributes": {...}}, ...]}
        return [feat["attributes"] for feat in data.get("features", [])]

    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        where = self._build_where(target)
        offset = 0
        total = 0

        self._logger.info(
            "Fetching %s assessor data for %s", self.source_name, target.label
        )

        while True:
            try:
                rows = self._fetch_page(where, offset)
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

    def _parse_row(self, row: dict) -> SourceRecord:
        c = self.COLUMNS
        number = str(row.get(c["street_number"]) or "").strip()
        name = str(row.get(c["street_name"]) or "").strip()
        suffix = str(row.get(c["street_suffix"]) or "").strip()
        street = " ".join(p for p in [number, name, suffix] if p)

        return SourceRecord(
            source_name=self.source_name,
            source_url=f"https://data.acgov.org/datasets/{self.ITEM_GUID}_{self.LAYER_INDEX}",
            raw_data=row,
            raw_address=street,
            raw_city=str(row.get(c["city"]) or ""),
            raw_state="CA",
            raw_zip=str(row.get(c["zip"]) or ""),
            raw_county="Alameda",
            apn=str(row.get(c["apn"]) or "") or None,
            units_raw=str(row.get(c["units"]) or "") or None,
            owner_name_raw=str(row.get(c["owner_name"]) or "") or None,
            mailing_address_raw=str(row.get(c["owner_address"]) or "") or None,
        )

    def is_available(self, target: GeographyTarget) -> bool:
        return (target.state or "").upper() in ("CA", "") and (
            (target.county or "").lower() in ("alameda", "alameda county", "")
            or any(z.startswith("946") for z in target.zips)
        )


# Keep old name as alias so registry.py doesn't break
AlamedaCountyAssessorCollector = AlamedaCountyArcGISAssessorCollector


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
