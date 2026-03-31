"""
Overture Maps Collector

Overture Maps Foundation releases open, freely licensed map data
including building footprints and Places data.

License: CDLA Permissive 2.0 (commercial use OK)
Source:  https://overturemaps.org/

This collector queries the Overture Maps Places dataset (via DuckDB
against their S3 release) to find apartment/multifamily buildings
in a target geography.

Requirements:
    pip install duckdb

Usage note:
    Overture data is released quarterly. This collector uses the
    latest release available. No API key required.
    Data is fetched directly from public S3.
"""

from __future__ import annotations

import json
from typing import Iterator, Optional

from .base import BaseCollector, GeographyTarget
from ..models import SourceRecord
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Overture Maps S3 path (update with each new release)
# See https://github.com/OvertureMaps/data for current path
OVERTURE_PLACES_S3 = (
    "s3://overturemaps-us-west-2/release/2024-09-18.0/theme=places/type=place/*"
)

APARTMENT_CATEGORIES = {
    "apartment_building",
    "apartment_complex",
    "apartment_rental_agency",
    "housing_complex",
    "residential_building",
}


class OvertureMapsCollector(BaseCollector):
    """
    Queries Overture Maps Places data via DuckDB (local, free, no auth).

    Config keys:
        overture_release (str): S3 path to release. Defaults to OVERTURE_PLACES_S3.
        min_units (int): Minimum number of units to include (best-effort).
    """

    source_name = "overture_maps"

    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        try:
            import duckdb  # type: ignore
        except ImportError:
            self._logger.warning(
                "duckdb not installed. Install with: pip install duckdb. "
                "Skipping Overture Maps collector."
            )
            return

        release_path = self._config.get("overture_release", OVERTURE_PLACES_S3)

        bbox = self._get_bbox(target)
        if not bbox:
            self._logger.warning(
                "OvertureMapsCollector requires a bounding box or city with known bbox. "
                "Provide bounding_box in GeographyTarget or add city lookup."
            )
            return

        min_lat, min_lon, max_lat, max_lon = bbox
        categories_str = ", ".join(f"'{c}'" for c in APARTMENT_CATEGORIES)

        query = f"""
            INSTALL httpfs;
            LOAD httpfs;
            SET s3_region='us-west-2';
            SELECT
                id,
                names.primary AS name,
                addresses[1].freeform AS address,
                addresses[1].locality AS city,
                addresses[1].region AS state,
                addresses[1].postcode AS zip,
                websites[1] AS website,
                phones[1] AS phone,
                categories.primary AS category,
                sources[1].record_id AS source_record,
                geometry
            FROM read_parquet('{release_path}', hive_partitioning=1)
            WHERE
                bbox.minx >= {min_lon}
                AND bbox.maxx <= {max_lon}
                AND bbox.miny >= {min_lat}
                AND bbox.maxy <= {max_lat}
                AND categories.primary IN ({categories_str})
        """

        self._logger.info(
            "Querying Overture Maps for %s (bbox: %s)", target.label, bbox
        )

        try:
            conn = duckdb.connect()
            rows = conn.execute(query).fetchall()
            col_names = [d[0] for d in conn.description]
        except Exception as exc:
            self._logger.error("Overture Maps query failed: %s", exc)
            return

        total = 0
        for row in rows:
            data = dict(zip(col_names, row))
            try:
                yield self._parse_row(data)
                total += 1
            except Exception as exc:
                self._logger.debug("Row parse error: %s | %s", exc, data)

        self._logger.info("Overture Maps: yielded %d records", total)

    def _parse_row(self, row: dict) -> SourceRecord:
        return SourceRecord(
            source_name=self.source_name,
            source_url="https://overturemaps.org/",
            raw_data=row,
            property_name=row.get("name"),
            raw_address=row.get("address", ""),
            raw_city=row.get("city", ""),
            raw_state=row.get("state", ""),
            raw_zip=row.get("zip", ""),
            website_raw=row.get("website"),
            phone_raw=row.get("phone"),
        )

    def _get_bbox(
        self, target: GeographyTarget
    ) -> Optional[tuple[float, float, float, float]]:
        if target.bounding_box:
            return target.bounding_box

        # Approximate bounding boxes for common California cities
        # TODO: Extend this lookup or integrate a geocoding service
        KNOWN_BBOXES: dict[str, tuple[float, float, float, float]] = {
            "oakland": (37.63, -122.35, 37.89, -122.11),
            "berkeley": (37.84, -122.33, 37.91, -122.23),
            "san francisco": (37.70, -122.53, 37.84, -122.35),
            "san jose": (37.22, -122.04, 37.47, -121.82),
            "sacramento": (38.43, -121.60, 38.68, -121.36),
            "los angeles": (33.70, -118.67, 34.34, -118.16),
            "long beach": (33.73, -118.27, 33.89, -118.06),
            "fresno": (36.66, -120.00, 36.90, -119.63),
        }
        city = (target.city or "").lower()
        return KNOWN_BBOXES.get(city)
