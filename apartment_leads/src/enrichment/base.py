"""
Base class for enrichment modules.

Enrichers take a PropertyLead (post-classification) and attempt to
fill in missing fields using public data sources.

Each enricher should:
  1. Only operate on leads in the LIKELY_OWNER_MANAGED bucket (by default)
  2. Respect rate limits and caching
  3. Store source attribution in EnrichedField objects
  4. Never overwrite a higher-confidence value
"""

from __future__ import annotations

import abc
from typing import Optional

from ..models import EnrichedField, ManagementStatus, PropertyLead
from ..utils.http import PoliteSession
from ..utils.logging import get_logger


class BaseEnricher(abc.ABC):
    """Abstract base class for enrichers."""

    enricher_name: str = "base"

    def __init__(
        self,
        session: Optional[PoliteSession] = None,
        config: Optional[dict] = None,
        target_statuses: Optional[list[ManagementStatus]] = None,
    ) -> None:
        self._session = session
        self._config = config or {}
        self._logger = get_logger(f"enricher.{self.enricher_name}")
        self._target_statuses = target_statuses or [
            ManagementStatus.LIKELY_OWNER_MANAGED,
            ManagementStatus.UNCLEAR,
        ]

    def should_enrich(self, lead: PropertyLead) -> bool:
        return lead.management_status in self._target_statuses

    @abc.abstractmethod
    def enrich(self, lead: PropertyLead) -> PropertyLead:
        """
        Enrich a single lead in-place. Return the (modified) lead.
        Must not raise; log errors and return lead unchanged on failure.
        """
        raise NotImplementedError

    def enrich_batch(self, leads: list[PropertyLead]) -> list[PropertyLead]:
        """Enrich all applicable leads in a list."""
        enriched_count = 0
        for lead in leads:
            if self.should_enrich(lead):
                self.enrich(lead)
                enriched_count += 1
        self._logger.info(
            "%s: enriched %d/%d leads", self.enricher_name, enriched_count, len(leads)
        )
        return leads

    @staticmethod
    def _set_if_better(
        current: Optional[EnrichedField],
        new_value: Optional[str],
        source: str,
        source_url: str,
        confidence: float,
    ) -> Optional[EnrichedField]:
        """
        Return new EnrichedField only if it has higher confidence than current.
        """
        if not new_value:
            return current
        if current and current.confidence >= confidence:
            return current
        from datetime import datetime
        return EnrichedField(
            value=new_value,
            source=source,
            source_url=source_url,
            fetched_at=datetime.utcnow(),
            confidence=confidence,
        )
