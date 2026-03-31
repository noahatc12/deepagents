"""
Rental Registry Collector

Many California cities maintain public rental registries.
These often list property owners, contact info, and unit counts.

Examples of cities with public registries:
  - Oakland (online search / CSV download)
  - Berkeley (public records request typically required)
  - Los Angeles (LAHD / ZIMAS)
  - San Jose (RSO registry)

This module provides concrete stubs for Oakland and a base class.
Add new registries by subclassing BaseRentalRegistryCollector.

IMPORTANT: Always check the city's Terms of Use before automated access.
Some registries allow bulk download; others require individual searches.
"""

from __future__ import annotations

import json
from typing import Iterator

from .base import BaseCollector, GeographyTarget
from ..models import SourceRecord
from ..utils.rate_limiter import with_retry


class BaseRentalRegistryCollector(BaseCollector):
    """
    Base class for city rental registry adapters.
    """

    source_name = "rental_registry_base"

    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        raise NotImplementedError


class OaklandRentalRegistryCollector(BaseRentalRegistryCollector):
    """
    Oakland Rent Adjustment Program (RAP) registry.

    Source:
        City of Oakland – Rent Adjustment Program
        https://www.oaklandca.gov/services/rent-adjustment-program
        Data endpoint: Oakland Open Data Portal (Socrata)
        https://data.oaklandca.gov/

    TODO:
        - Find or confirm the dataset ID on data.oaklandca.gov
        - Verify available columns (unit_count, owner_name, address)
        - Confirm open data license / terms

    Notes:
        Oakland's RAP registry covers units under rent control.
        Properties built after 1983 are generally excluded.
        Use assessor data for a complete picture.
    """

    source_name = "oakland_rental_registry"
    BASE_URL = "https://data.oaklandca.gov/resource"
    DATASET_ID = "5dsi-8gtf"  # Oakland Residential Rental Property List
    PAGE_SIZE = 1000

    @with_retry(max_attempts=4, base_delay=2.0)
    def _fetch_page(self, offset: int) -> list[dict]:
        if not self._session:
            raise RuntimeError("No HTTP session")
        url = f"{self.BASE_URL}/{self.DATASET_ID}.json"
        params = {
            "$limit": self.PAGE_SIZE,
            "$offset": offset,
            "$order": ":id",
        }
        text = self._session.get(url, params=params)
        return json.loads(text)

    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        if "TODO" in self.DATASET_ID:
            self._logger.warning(
                "%s: DATASET_ID not configured – skipping. "
                "Set the Socrata dataset ID in the collector.",
                self.source_name,
            )
            return

        offset = 0
        total = 0
        self._logger.info("Fetching Oakland RAP registry data")

        while True:
            try:
                rows = self._fetch_page(offset)
            except Exception as exc:
                self._logger.error("Oakland registry fetch failed: %s", exc)
                break

            if not rows:
                break

            for row in rows:
                try:
                    yield self._parse_row(row)
                    total += 1
                except Exception as exc:
                    self._logger.debug("Row parse error: %s", exc)

            if len(rows) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE

        self._logger.info("Oakland registry: yielded %d records", total)

    def _parse_row(self, row: dict) -> SourceRecord:
        # TODO: Update column names once dataset is confirmed
        return SourceRecord(
            source_name=self.source_name,
            source_url=f"https://data.oaklandca.gov/resource/{self.DATASET_ID}",
            raw_data=row,
            raw_address=row.get("address", row.get("property_address", "")),
            raw_city="Oakland",
            raw_state="CA",
            raw_zip=row.get("zip", row.get("zip_code", "")),
            raw_county="Alameda",
            property_name=row.get("property_name") or None,
            units_raw=row.get("units", row.get("unit_count", "")) or None,
            owner_name_raw=row.get("owner_name") or None,
            phone_raw=row.get("phone") or None,
        )

    def is_available(self, target: GeographyTarget) -> bool:
        return (target.city or "").lower() in ("oakland", "")


class BerkeleyRentalRegistryCollector(BaseRentalRegistryCollector):
    """
    Berkeley Rent Stabilization Board registry.

    Source:
        City of Berkeley – Rent Stabilization Board
        https://rentboard.cityofberkeley.info/

    TODO:
        - Confirm public data availability (may require PRA request)
        - Implement CSV download or API endpoint if available
        - Add address parsing for Berkeley format
    """

    source_name = "berkeley_rental_registry"

    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        self._logger.info(
            "Berkeley rental registry: No automated endpoint currently configured. "
            "Data may be available via public records request or CSV download. "
            "Use the csv_import collector with a downloaded registry file."
        )
        return
        yield  # make it a generator

    def is_available(self, target: GeographyTarget) -> bool:
        return (target.city or "").lower() in ("berkeley", "")
