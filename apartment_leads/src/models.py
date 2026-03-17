"""
Core data models for the apartment lead generation pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ManagementStatus(str, Enum):
    LIKELY_THIRD_PARTY = "likely_third_party"
    LIKELY_OWNER_MANAGED = "likely_owner_managed"
    UNCLEAR = "unclear"
    NEEDS_REVIEW = "needs_review"


class ConfidenceLevel(str, Enum):
    HIGH = "high"       # >= 0.80
    MEDIUM = "medium"   # 0.50 – 0.79
    LOW = "low"         # < 0.50


@dataclass
class SourceRecord:
    """A raw record as pulled from one source adapter."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = ""          # e.g. "alameda_assessor", "csv_import"
    source_url: str = ""
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    raw_data: dict[str, Any] = field(default_factory=dict)

    # Address fields as returned by the source
    raw_address: str = ""
    raw_city: str = ""
    raw_state: str = ""
    raw_zip: str = ""
    raw_county: str = ""

    # Optional structured fields present in source
    property_name: Optional[str] = None
    units_raw: Optional[str] = None
    owner_name_raw: Optional[str] = None
    owner_entity_raw: Optional[str] = None
    mailing_address_raw: Optional[str] = None
    website_raw: Optional[str] = None
    phone_raw: Optional[str] = None
    management_name_raw: Optional[str] = None
    apn: Optional[str] = None  # Assessor Parcel Number


@dataclass
class EnrichedField:
    """Wraps a single enriched value with provenance."""

    value: Optional[str]
    source: str
    source_url: str = ""
    fetched_at: Optional[datetime] = None
    confidence: float = 0.0  # 0.0 – 1.0


@dataclass
class PropertyLead:
    """
    A normalized, deduplicated, classified, and enriched property record.
    This is the canonical output object.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Normalized address
    property_name: Optional[str] = None
    street_address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    county: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Property details
    apn: Optional[str] = None
    units_estimated: Optional[int] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None  # e.g. "apartment", "multifamily"

    # Contact / web
    website: Optional[str] = None
    phone: Optional[str] = None

    # Management classification
    management_status: ManagementStatus = ManagementStatus.UNCLEAR
    management_status_confidence: float = 0.0
    management_status_confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    detected_management_company: Optional[str] = None
    management_signals: list[str] = field(default_factory=list)

    # Owner / entity enrichment
    owner_name: Optional[EnrichedField] = None
    owner_entity: Optional[EnrichedField] = None
    owner_contact_name: Optional[EnrichedField] = None
    owner_email: Optional[EnrichedField] = None
    owner_phone: Optional[EnrichedField] = None
    mailing_address: Optional[EnrichedField] = None

    # Provenance
    source_ids: list[str] = field(default_factory=list)  # SourceRecord IDs
    source_urls: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)

    # Review
    manual_review_flag: bool = False
    review_reason: Optional[str] = None
    notes: str = ""

    @property
    def full_address(self) -> str:
        parts = [self.street_address, self.city, self.state, self.zip_code]
        return ", ".join(p for p in parts if p)

    def to_flat_dict(self) -> dict[str, Any]:
        """Return a flat dictionary suitable for CSV/Excel export."""

        def ev(field: Optional[EnrichedField]) -> Optional[str]:
            return field.value if field else None

        def ec(field: Optional[EnrichedField]) -> float:
            return field.confidence if field else 0.0

        return {
            "property_name": self.property_name,
            "street_address": self.street_address,
            "city": self.city,
            "state": self.state,
            "zip": self.zip_code,
            "county": self.county,
            "apn": self.apn,
            "units_estimated": self.units_estimated,
            "year_built": self.year_built,
            "website": self.website,
            "phone": self.phone,
            "management_status": self.management_status.value,
            "management_status_confidence": round(self.management_status_confidence, 3),
            "detected_management_company": self.detected_management_company,
            "management_signals": "; ".join(self.management_signals),
            "owner_name": ev(self.owner_name),
            "owner_entity": ev(self.owner_entity),
            "owner_contact_name": ev(self.owner_contact_name),
            "owner_email": ev(self.owner_email),
            "owner_phone": ev(self.owner_phone),
            "mailing_address": ev(self.mailing_address),
            "owner_name_confidence": ec(self.owner_name),
            "owner_entity_confidence": ec(self.owner_entity),
            "source_urls": " | ".join(self.source_urls),
            "source_names": " | ".join(self.source_names),
            "manual_review_flag": self.manual_review_flag,
            "review_reason": self.review_reason,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
