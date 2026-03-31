"""
Enrichment pipeline runner.

Runs all configured enrichers in sequence against the lead list.
Only enriches leads in target management statuses.
"""

from __future__ import annotations

from typing import Optional

from .base import BaseEnricher
from .ca_sos import CaSosEnricher
from .opencorporates import OpenCorporatesEnricher
from ..models import PropertyLead
from ..utils.http import PoliteSession
from ..utils.logging import get_logger

logger = get_logger(__name__)


def build_enrichers(
    session: Optional[PoliteSession] = None,
    config: Optional[dict] = None,
    enabled: Optional[list[str]] = None,
) -> list[BaseEnricher]:
    """
    Instantiate and return the list of enrichers to run.

    Args:
        session: Shared HTTP session.
        config:  Top-level config dict with per-enricher sub-dicts.
        enabled: List of enricher names to enable. None = all.
    """
    config = config or {}
    all_enrichers: list[BaseEnricher] = [
        CaSosEnricher(session=session, config=config.get("ca_sos", {})),
        OpenCorporatesEnricher(
            session=session, config=config.get("opencorporates", {})
        ),
    ]

    if enabled is None:
        return all_enrichers

    return [e for e in all_enrichers if e.enricher_name in enabled]


def run_enrichment(
    leads: list[PropertyLead],
    enrichers: Optional[list[BaseEnricher]] = None,
    session: Optional[PoliteSession] = None,
    config: Optional[dict] = None,
) -> list[PropertyLead]:
    """
    Run all enrichers against the lead list.
    Returns the (mutated) leads list.
    """
    if enrichers is None:
        enrichers = build_enrichers(session=session, config=config)

    if not enrichers:
        logger.info("No enrichers configured – skipping enrichment")
        return leads

    logger.info("Running %d enricher(s) on %d leads", len(enrichers), len(leads))
    for enricher in enrichers:
        try:
            enricher.enrich_batch(leads)
        except Exception as exc:
            logger.error("Enricher %s crashed: %s", enricher.enricher_name, exc)

    return leads
