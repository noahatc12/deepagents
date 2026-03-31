"""
Normalization and deduplication pipeline.

Takes raw SourceRecords from collectors and produces a deduplicated
list of PropertyLead objects ready for classification.

Deduplication key: address_fingerprint (street + city + state + zip)
When duplicates are found, fields are merged with a priority order
based on source trust (assessor > registry > csv > map).
"""

from __future__ import annotations

import re
from typing import Optional

from ..models import PropertyLead, SourceRecord
from ..utils.address import (
    address_fingerprint,
    normalize_address_full,
    normalize_state,
    normalize_zip,
    normalize_phone,
)
from ..utils.entity import normalize_entity_name
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Source trust order (higher index = higher trust when merging)
SOURCE_PRIORITY = [
    "overture_maps",
    "csv_import",
    "oakland_rental_registry",
    "berkeley_rental_registry",
    "sacramento_assessor",
    "alameda_assessor",
]


def _source_priority(source_name: str) -> int:
    try:
        return SOURCE_PRIORITY.index(source_name)
    except ValueError:
        return 0


def _parse_units(raw: Optional[str]) -> Optional[int]:
    """Extract integer unit count from raw string."""
    if not raw:
        return None
    match = re.search(r"\b(\d+)\b", str(raw))
    return int(match.group(1)) if match else None


def _normalize_url(raw: Optional[str]) -> Optional[str]:
    """Clean up a URL string."""
    if not raw:
        return None
    url = raw.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url or None


class NormalizationPipeline:
    """
    Converts SourceRecords into PropertyLead objects and deduplicates them.

    Usage:
        pipe = NormalizationPipeline()
        leads = pipe.run(source_records)
    """

    def run(self, records: list[SourceRecord]) -> list[PropertyLead]:
        """
        Normalize and deduplicate a list of SourceRecords.
        Returns a list of unique PropertyLead objects.
        """
        logger.info("Normalizing %d raw records", len(records))

        # Normalize each record to a PropertyLead
        normalized: list[tuple[str, PropertyLead, str]] = []  # (fingerprint, lead, source_name)
        skipped = 0

        for record in records:
            lead, fp = self._normalize_record(record)
            if fp:
                normalized.append((fp, lead, record.source_name))
            else:
                skipped += 1

        logger.info("Skipped %d records with no parseable address", skipped)

        # Deduplicate by fingerprint
        deduped = self._deduplicate(normalized)
        logger.info(
            "Deduplication: %d raw -> %d unique properties",
            len(normalized),
            len(deduped),
        )
        return list(deduped.values())

    def _normalize_record(
        self, record: SourceRecord
    ) -> tuple[PropertyLead, str]:
        """Return (PropertyLead, fingerprint). Fingerprint is '' if address unusable."""

        street = normalize_address_full(record.raw_address)
        city = record.raw_city.strip().lower()
        state = normalize_state(record.raw_state)
        zip_code = normalize_zip(record.raw_zip)
        county = record.raw_county.strip().title()

        fp = address_fingerprint(street, city, state, zip_code)
        if not fp.replace("|", "").strip():
            return PropertyLead(), ""

        lead = PropertyLead(
            property_name=record.property_name,
            street_address=street.title() if street else "",
            city=city.title(),
            state=state.upper(),
            zip_code=zip_code,
            county=county,
            apn=record.apn,
            units_estimated=_parse_units(record.units_raw),
            website=_normalize_url(record.website_raw),
            phone=normalize_phone(record.phone_raw or ""),
            source_ids=[record.id],
            source_urls=[record.source_url] if record.source_url else [],
            source_names=[record.source_name],
        )

        # Owner fields (without enrichment yet)
        if record.owner_name_raw:
            from ..models import EnrichedField
            lead.owner_name = EnrichedField(
                value=normalize_entity_name(record.owner_name_raw).title(),
                source=record.source_name,
                source_url=record.source_url,
                fetched_at=record.fetched_at,
                confidence=0.7,  # Assessor data is moderately reliable
            )
        if record.owner_entity_raw:
            from ..models import EnrichedField
            lead.owner_entity = EnrichedField(
                value=normalize_entity_name(record.owner_entity_raw).upper(),
                source=record.source_name,
                source_url=record.source_url,
                fetched_at=record.fetched_at,
                confidence=0.7,
            )
        if record.mailing_address_raw:
            from ..models import EnrichedField
            lead.mailing_address = EnrichedField(
                value=record.mailing_address_raw.strip(),
                source=record.source_name,
                source_url=record.source_url,
                fetched_at=record.fetched_at,
                confidence=0.8,
            )

        return lead, fp

    def _deduplicate(
        self, normalized: list[tuple[str, PropertyLead, str]]
    ) -> dict[str, PropertyLead]:
        """
        Merge records with the same address fingerprint.
        Higher-priority sources win for scalar fields.
        Lists (source_urls, etc.) are unioned.
        """
        groups: dict[str, list[tuple[PropertyLead, str]]] = {}
        for fp, lead, source_name in normalized:
            groups.setdefault(fp, []).append((lead, source_name))

        result: dict[str, PropertyLead] = {}

        for fp, group in groups.items():
            # Sort by source priority descending (highest trust last = wins)
            group.sort(key=lambda x: _source_priority(x[1]))
            merged = group[0][0]  # start with lowest priority

            for lead, source_name in group[1:]:
                merged = self._merge(merged, lead)

            result[fp] = merged

        return result

    def _merge(self, base: PropertyLead, update: PropertyLead) -> PropertyLead:
        """Merge update into base, preferring update's non-empty values."""

        def prefer(a, b):
            """Return b if b is non-empty, else a."""
            if isinstance(b, str):
                return b if b.strip() else a
            return b if b is not None else a

        base.property_name = prefer(base.property_name, update.property_name)
        base.street_address = prefer(base.street_address, update.street_address)
        base.city = prefer(base.city, update.city)
        base.state = prefer(base.state, update.state)
        base.zip_code = prefer(base.zip_code, update.zip_code)
        base.county = prefer(base.county, update.county)
        base.apn = prefer(base.apn, update.apn)
        base.units_estimated = prefer(base.units_estimated, update.units_estimated)
        base.website = prefer(base.website, update.website)
        base.phone = prefer(base.phone, update.phone)

        # Merge enriched fields (take higher confidence)
        def merge_enriched(a, b):
            if a is None:
                return b
            if b is None:
                return a
            return b if b.confidence >= a.confidence else a

        base.owner_name = merge_enriched(base.owner_name, update.owner_name)
        base.owner_entity = merge_enriched(base.owner_entity, update.owner_entity)
        base.mailing_address = merge_enriched(base.mailing_address, update.mailing_address)

        # Union provenance lists
        base.source_ids = list(dict.fromkeys(base.source_ids + update.source_ids))
        base.source_urls = list(dict.fromkeys(base.source_urls + update.source_urls))
        base.source_names = list(dict.fromkeys(base.source_names + update.source_names))

        return base
