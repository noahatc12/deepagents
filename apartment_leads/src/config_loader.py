"""
Config file loader for YAML-based pipeline configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .collectors.base import GeographyTarget
from .pipeline import PipelineConfig


def load_pipeline_config(cfg: dict[str, Any]) -> PipelineConfig:
    """
    Build a PipelineConfig from a parsed YAML config dict.

    See configs/east_bay.yaml for a complete example.
    """
    geo = cfg.get("geography", {})
    bbox = geo.get("bounding_box")
    if bbox:
        bbox = tuple(float(x) for x in bbox)

    target = GeographyTarget(
        city=geo.get("city"),
        county=geo.get("county"),
        state=geo.get("state", "CA"),
        zips=geo.get("zips", []),
        metro=geo.get("metro"),
        bounding_box=bbox,
    )

    sources = cfg.get("sources", {})
    output = cfg.get("output", {})
    enrichment = cfg.get("enrichment", {})
    pipeline = cfg.get("pipeline", {})

    csv_path = sources.get("csv_import", {}).get("csv_path")

    return PipelineConfig(
        target=target,
        enabled_sources=sources.get("enabled"),
        collector_configs=sources.get("configs", {}),
        csv_import_path=Path(csv_path) if csv_path else None,
        requests_per_second=pipeline.get("requests_per_second", 0.5),
        cache_db_path=Path(pipeline.get("cache_db", "data/cache/requests.db")),
        cache_ttl_seconds=pipeline.get("cache_ttl_seconds", 86400),
        enabled_enrichers=enrichment.get("enabled"),
        enricher_configs=enrichment.get("configs", {}),
        unclear_threshold=pipeline.get("unclear_threshold", 0.2),
        run_llm_review=pipeline.get("run_llm_review", False),
        output_dir=Path(output.get("dir", "data/processed")),
        export_csv=output.get("csv", True),
        export_excel=output.get("excel", True),
        export_json=output.get("json", True),
        export_review_queue=output.get("review_queue", True),
        export_sqlite=output.get("sqlite", True),
        db_path=Path(output["db_path"]) if output.get("db_path") else None,
        filter_third_party=pipeline.get("filter_third_party", True),
        min_units=pipeline.get("min_units"),
        log_level=pipeline.get("log_level", "INFO"),
        log_file=Path(pipeline["log_file"]) if pipeline.get("log_file") else None,
    )
