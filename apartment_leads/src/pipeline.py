"""
Main pipeline orchestrator.

Ties together: collection → normalization → classification → enrichment → export.

Usage:
    from src.pipeline import Pipeline, PipelineConfig
    config = PipelineConfig(...)
    results = Pipeline(config).run()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .collectors.base import GeographyTarget
from .collectors.registry import get_collectors_for_target
from .normalizers.pipeline import NormalizationPipeline
from .classifiers.management import ManagementClassifier, classify_leads
from .enrichment.pipeline import run_enrichment, build_enrichers
from .exports.csv_export import export_csv, export_excel, export_json, export_review_queue
from .exports.database import LeadDatabase
from .models import ManagementStatus, PropertyLead
from .utils.http import make_session
from .utils.logging import get_logger
from .utils.cache import RequestCache

logger = get_logger(__name__)


@dataclass
class PipelineConfig:
    """Full configuration for a pipeline run."""

    # Geography
    target: GeographyTarget

    # Source selection
    enabled_sources: Optional[list[str]] = None       # None = all applicable
    collector_configs: dict[str, dict] = field(default_factory=dict)
    csv_import_path: Optional[Path] = None

    # HTTP
    requests_per_second: float = 0.5
    cache_db_path: Optional[Path] = Path("data/cache/requests.db")
    cache_ttl_seconds: int = 86_400  # 24h

    # Enrichment
    enabled_enrichers: Optional[list[str]] = None     # None = all
    enricher_configs: dict[str, dict] = field(default_factory=dict)

    # Classification
    unclear_threshold: float = 0.2
    run_llm_review: bool = False
    llm_reviewer: Optional[object] = None  # Implements LLMReviewerProtocol

    # Export
    output_dir: Path = Path("data/processed")
    export_csv: bool = True
    export_excel: bool = True
    export_json: bool = True
    export_review_queue: bool = True
    export_sqlite: bool = True
    db_path: Optional[Path] = None

    # Filtering
    filter_third_party: bool = True  # Exclude likely-third-party from final export
    min_units: Optional[int] = None  # Filter out properties below this unit count

    # Logging
    log_file: Optional[Path] = None
    log_level: str = "INFO"

    @property
    def run_label(self) -> str:
        t = self.target
        parts = [t.city or t.county or (t.metro or ""), t.state or ""]
        return "_".join(p.lower().replace(" ", "_") for p in parts if p)


@dataclass
class PipelineResult:
    total_collected: int = 0
    total_normalized: int = 0
    total_classified: int = 0
    total_enriched: int = 0
    total_exported: int = 0
    leads: list[PropertyLead] = field(default_factory=list)
    output_files: list[Path] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class Pipeline:
    """
    Orchestrates the full apartment lead-generation pipeline.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._logger = get_logger("pipeline", log_file=config.log_file, level=config.log_level)

    def run(self) -> PipelineResult:
        t0 = time.monotonic()
        result = PipelineResult()
        cfg = self.config

        self._logger.info("=" * 60)
        self._logger.info("Pipeline start – target: %s", cfg.target.label)
        self._logger.info("=" * 60)

        # 1. HTTP session + cache
        session = make_session(
            cache_db=cfg.cache_db_path,
            cache_ttl=cfg.cache_ttl_seconds,
            requests_per_second=cfg.requests_per_second,
        )

        # 2. Collection
        collector_configs = dict(cfg.collector_configs)
        if cfg.csv_import_path:
            collector_configs["csv_import"] = {"csv_path": str(cfg.csv_import_path)}

        collectors = get_collectors_for_target(
            cfg.target,
            enabled_sources=cfg.enabled_sources,
            session=session,
            configs=collector_configs,
        )

        raw_records = []
        for collector in collectors:
            self._logger.info("Running collector: %s", collector.source_name)
            try:
                recs = list(collector.collect(cfg.target))
                self._logger.info("  -> %d records", len(recs))
                raw_records.extend(recs)
            except Exception as exc:
                self._logger.error("Collector %s failed: %s", collector.source_name, exc)

        result.total_collected = len(raw_records)
        self._logger.info("Total raw records collected: %d", result.total_collected)

        if not raw_records:
            self._logger.warning("No records collected – check collector configs and geography.")
            result.elapsed_seconds = time.monotonic() - t0
            return result

        # 3. Normalization + deduplication
        self._logger.info("Running normalization pipeline ...")
        norm = NormalizationPipeline()
        leads = norm.run(raw_records)
        result.total_normalized = len(leads)
        self._logger.info("Normalized to %d unique properties", result.total_normalized)

        # 4. Unit count filter
        if cfg.min_units:
            before = len(leads)
            leads = [
                l for l in leads
                if l.units_estimated is None or l.units_estimated >= cfg.min_units
            ]
            self._logger.info(
                "Min-units filter (%d+): %d -> %d", cfg.min_units, before, len(leads)
            )

        # 5. Management classification
        self._logger.info("Running management classifier ...")
        clf = ManagementClassifier(unclear_threshold=cfg.unclear_threshold)
        leads = classify_leads(leads, classifier=clf)
        result.total_classified = len(leads)

        if cfg.run_llm_review and cfg.llm_reviewer:
            from .classifiers.management import llm_review_leads
            leads = llm_review_leads(leads, cfg.llm_reviewer)

        # Count by status
        status_counts = {}
        for lead in leads:
            status_counts[lead.management_status.value] = (
                status_counts.get(lead.management_status.value, 0) + 1
            )
        for status, count in sorted(status_counts.items()):
            self._logger.info("  %s: %d", status, count)

        # 6. Enrichment (owner-managed and unclear leads only)
        self._logger.info("Running enrichment ...")
        enrichers = build_enrichers(
            session=session,
            config=cfg.enricher_configs,
            enabled=cfg.enabled_enrichers,
        )
        leads = run_enrichment(leads, enrichers=enrichers)
        result.total_enriched = len(leads)

        # 7. Filter third-party for export
        export_leads = leads
        if cfg.filter_third_party:
            before = len(export_leads)
            export_leads = [
                l for l in export_leads
                if l.management_status != ManagementStatus.LIKELY_THIRD_PARTY
            ]
            self._logger.info(
                "Filtered third-party: %d -> %d leads for export", before, len(export_leads)
            )

        result.leads = export_leads
        result.total_exported = len(export_leads)

        # 8. Export
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        label = cfg.run_label or "leads"
        output_files = []

        if cfg.export_csv:
            p = cfg.output_dir / f"{label}_leads.csv"
            export_csv(export_leads, p)
            output_files.append(p)

        if cfg.export_excel:
            p = cfg.output_dir / f"{label}_leads.xlsx"
            export_excel(export_leads, p)
            output_files.append(p)

        if cfg.export_json:
            p = cfg.output_dir / f"{label}_leads.json"
            export_json(export_leads, p)
            output_files.append(p)

        if cfg.export_review_queue:
            p = cfg.output_dir / f"{label}_review_queue.csv"
            export_review_queue(export_leads, p)
            output_files.append(p)

        if cfg.export_sqlite:
            db_path = cfg.db_path or cfg.output_dir / "leads.db"
            db = LeadDatabase(db_path)
            db.upsert_leads(export_leads)
            db.close()
            output_files.append(db_path)

        session.close()

        result.output_files = output_files
        result.elapsed_seconds = time.monotonic() - t0

        self._logger.info("=" * 60)
        self._logger.info(
            "Pipeline complete in %.1fs – %d leads exported",
            result.elapsed_seconds,
            result.total_exported,
        )
        for f in output_files:
            self._logger.info("  -> %s", f)
        self._logger.info("=" * 60)

        return result
