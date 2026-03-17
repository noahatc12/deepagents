"""
Base class for all source adapters / collectors.

Each collector is responsible for:
  1. Accepting a GeographyTarget config
  2. Fetching raw records from one public data source
  3. Returning a list of SourceRecord objects

New markets or sources are added by subclassing BaseCollector and
registering via the COLLECTOR_REGISTRY in registry.py.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Iterator, Optional

from ..models import SourceRecord
from ..utils.http import PoliteSession
from ..utils.logging import get_logger


@dataclass
class GeographyTarget:
    """
    Describes the target geography for a pipeline run.
    At least one of city/county/zips must be provided.
    """

    city: Optional[str] = None
    county: Optional[str] = None
    state: str = ""
    zips: list[str] = field(default_factory=list)
    metro: Optional[str] = None
    # Optional bounding box: (min_lat, min_lon, max_lat, max_lon)
    bounding_box: Optional[tuple[float, float, float, float]] = None

    def __post_init__(self) -> None:
        if not any([self.city, self.county, self.zips, self.metro]):
            raise ValueError(
                "GeographyTarget requires at least one of: city, county, zips, metro"
            )

    @property
    def label(self) -> str:
        parts = [self.city, self.county, self.state]
        return ", ".join(p for p in parts if p)


class BaseCollector(abc.ABC):
    """
    Abstract base class for all data source adapters.

    Subclasses must implement:
        - source_name (class attribute)
        - collect(target) -> Iterator[SourceRecord]
    """

    source_name: str = "base"

    def __init__(
        self,
        session: Optional[PoliteSession] = None,
        config: Optional[dict] = None,
    ) -> None:
        self._session = session
        self._config = config or {}
        self._logger = get_logger(f"collector.{self.source_name}")

    @abc.abstractmethod
    def collect(self, target: GeographyTarget) -> Iterator[SourceRecord]:
        """
        Yield SourceRecord objects for the given geography.
        Must be a generator; may yield partial results before failure.
        """
        raise NotImplementedError

    def is_available(self, target: GeographyTarget) -> bool:
        """
        Return True if this collector is applicable for the given geography.
        Override in subclasses for jurisdiction-specific sources.
        """
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source_name!r})"
