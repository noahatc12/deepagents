"""
Collector Registry

Central registry of all available source adapters.
The pipeline uses this to select which collectors to run
for a given geography.
"""

from __future__ import annotations

from typing import Optional, Type

from .base import BaseCollector, GeographyTarget
from .csv_import import CsvImportCollector
from .assessor import AlamedaCountyAssessorCollector, SacramentoCountyAssessorCollector
from .rental_registry import (
    OaklandRentalRegistryCollector,
    BerkeleyRentalRegistryCollector,
)
from .overture_maps import OvertureMapsCollector
from ..utils.http import PoliteSession
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Map of source_name -> collector class
COLLECTOR_REGISTRY: dict[str, Type[BaseCollector]] = {
    CsvImportCollector.source_name: CsvImportCollector,
    AlamedaCountyAssessorCollector.source_name: AlamedaCountyAssessorCollector,
    SacramentoCountyAssessorCollector.source_name: SacramentoCountyAssessorCollector,
    OaklandRentalRegistryCollector.source_name: OaklandRentalRegistryCollector,
    BerkeleyRentalRegistryCollector.source_name: BerkeleyRentalRegistryCollector,
    OvertureMapsCollector.source_name: OvertureMapsCollector,
}


def get_collectors_for_target(
    target: GeographyTarget,
    enabled_sources: Optional[list[str]] = None,
    session: Optional[PoliteSession] = None,
    configs: Optional[dict[str, dict]] = None,
) -> list[BaseCollector]:
    """
    Return instantiated collectors applicable to the target geography.

    Args:
        target:          The geography to collect data for.
        enabled_sources: Optional allowlist of source names. If None, all
                         applicable collectors are returned.
        session:         Shared HTTP session.
        configs:         Per-source config dicts, keyed by source_name.
    """
    configs = configs or {}
    selected = []

    for name, cls in COLLECTOR_REGISTRY.items():
        if enabled_sources is not None and name not in enabled_sources:
            continue
        instance = cls(session=session, config=configs.get(name, {}))
        if instance.is_available(target):
            selected.append(instance)
            logger.debug("Registered collector: %s", name)
        else:
            logger.debug("Collector %s not applicable for %s", name, target.label)

    logger.info(
        "Selected %d collector(s) for %s: %s",
        len(selected),
        target.label,
        [c.source_name for c in selected],
    )
    return selected
