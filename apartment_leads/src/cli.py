"""
CLI entry point for the apartment lead-generation pipeline.

Usage examples:

  # Run against Oakland with default sources
  python -m apartment_leads run --city Oakland --state CA

  # Run with specific ZIP codes
  python -m apartment_leads run --zips 94601,94602,94603 --state CA

  # Run with a CSV file import
  python -m apartment_leads run --city Oakland --state CA --csv my_props.csv

  # Run with a specific config file
  python -m apartment_leads run --config configs/east_bay.yaml

  # Query the local database
  python -m apartment_leads query --status likely_owner_managed --city Oakland

  # Show pipeline stats from last run
  python -m apartment_leads stats
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .collectors.base import GeographyTarget
from .pipeline import Pipeline, PipelineConfig
from .utils.logging import get_logger

logger = get_logger("cli")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="apartment_leads",
        description="Apartment building lead-generation pipeline.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Sub-command")

    # ---- run ----
    run_parser = subparsers.add_parser("run", help="Run the full pipeline")

    # Geography
    geo_group = run_parser.add_argument_group("Geography (at least one required)")
    geo_group.add_argument("--city", help="Target city name")
    geo_group.add_argument("--county", help="Target county name")
    geo_group.add_argument("--state", default="CA", help="State abbreviation (default: CA)")
    geo_group.add_argument(
        "--zips", help="Comma-separated ZIP codes, e.g. 94601,94602"
    )
    geo_group.add_argument("--metro", help="Metro area name")
    geo_group.add_argument(
        "--bbox",
        help="Bounding box: min_lat,min_lon,max_lat,max_lon",
    )

    # Config
    run_parser.add_argument(
        "--config", type=Path, help="Path to YAML config file (overrides CLI args)"
    )

    # Sources
    run_parser.add_argument(
        "--sources",
        help="Comma-separated list of source names to enable (default: all applicable)",
    )
    run_parser.add_argument(
        "--csv", dest="csv_path", type=Path, help="Path to CSV file for csv_import collector"
    )

    # Output
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Output directory (default: data/processed)",
    )
    run_parser.add_argument(
        "--no-excel", action="store_true", help="Skip Excel export"
    )
    run_parser.add_argument(
        "--no-sqlite", action="store_true", help="Skip SQLite export"
    )
    run_parser.add_argument(
        "--include-third-party",
        action="store_true",
        help="Include likely-third-party managed properties in export",
    )
    run_parser.add_argument(
        "--min-units",
        type=int,
        default=None,
        help="Minimum unit count filter (e.g. 5 for 5+ unit buildings)",
    )

    # Misc
    run_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    run_parser.add_argument(
        "--log-file", type=Path, help="Write logs to this file in addition to stdout"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and list collectors without fetching data",
    )

    # ---- query ----
    q_parser = subparsers.add_parser("query", help="Query the local SQLite database")
    q_parser.add_argument(
        "--db", type=Path, default=Path("data/processed/leads.db"), help="Database path"
    )
    q_parser.add_argument(
        "--status",
        choices=["likely_owner_managed", "likely_third_party", "unclear", "needs_review"],
    )
    q_parser.add_argument("--city", help="Filter by city")
    q_parser.add_argument("--state", help="Filter by state")
    q_parser.add_argument("--zip", dest="zip_code", help="Filter by ZIP")
    q_parser.add_argument("--review-only", action="store_true", help="Only show review-flagged leads")
    q_parser.add_argument("--limit", type=int, default=50)

    # ---- stats ----
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.add_argument(
        "--db", type=Path, default=Path("data/processed/leads.db")
    )

    return parser.parse_args(argv)


def cmd_run(args: argparse.Namespace) -> int:
    # Load config from YAML if provided
    if args.config:
        return _run_from_config_file(args)

    # Build geography target
    try:
        bbox = None
        if getattr(args, "bbox", None):
            parts = [float(x) for x in args.bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox must have 4 comma-separated values")
            bbox = tuple(parts)

        target = GeographyTarget(
            city=args.city,
            county=args.county,
            state=args.state or "CA",
            zips=[z.strip() for z in (args.zips or "").split(",") if z.strip()],
            metro=args.metro,
            bounding_box=bbox,
        )
    except ValueError as exc:
        logger.error("Invalid geography arguments: %s", exc)
        return 1

    enabled_sources = (
        [s.strip() for s in args.sources.split(",") if s.strip()]
        if getattr(args, "sources", None)
        else None
    )

    pipeline_config = PipelineConfig(
        target=target,
        enabled_sources=enabled_sources,
        csv_import_path=getattr(args, "csv_path", None),
        output_dir=args.output_dir,
        export_excel=not args.no_excel,
        export_sqlite=not args.no_sqlite,
        filter_third_party=not args.include_third_party,
        min_units=args.min_units,
        log_level=args.log_level,
        log_file=getattr(args, "log_file", None),
    )

    if args.dry_run:
        from .collectors.registry import get_collectors_for_target
        collectors = get_collectors_for_target(target, enabled_sources=enabled_sources)
        print(f"\nDry run – Target: {target.label}")
        print(f"Would run {len(collectors)} collector(s):")
        for c in collectors:
            print(f"  - {c.source_name}")
        print("\nNo data fetched. Remove --dry-run to execute.\n")
        return 0

    result = Pipeline(pipeline_config).run()
    print(f"\nDone! {result.total_exported} leads exported in {result.elapsed_seconds:.1f}s")
    for f in result.output_files:
        print(f"  -> {f}")
    return 0


def _run_from_config_file(args: argparse.Namespace) -> int:
    try:
        import yaml
    except ImportError:
        logger.error("PyYAML not installed. Run: pip install pyyaml")
        return 1

    try:
        with open(args.config) as fh:
            cfg_dict = yaml.safe_load(fh)
    except Exception as exc:
        logger.error("Failed to load config file %s: %s", args.config, exc)
        return 1

    from .config_loader import load_pipeline_config
    try:
        pipeline_config = load_pipeline_config(cfg_dict)
    except Exception as exc:
        logger.error("Invalid config: %s", exc)
        return 1

    result = Pipeline(pipeline_config).run()
    print(f"\nDone! {result.total_exported} leads exported in {result.elapsed_seconds:.1f}s")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"Database not found: {args.db}")
        print("Run 'apartment_leads run ...' first to populate the database.")
        return 1

    from .exports.database import LeadDatabase
    db = LeadDatabase(args.db)

    leads = list(db.query(
        management_status=args.status,
        city=args.city,
        state=args.state,
        zip_code=args.zip_code,
        manual_review_only=args.review_only,
        limit=args.limit,
    ))
    db.close()

    if not leads:
        print("No leads found matching filters.")
        return 0

    for lead in leads:
        status_icon = {
            "likely_owner_managed": "✓",
            "likely_third_party": "✗",
            "unclear": "?",
            "needs_review": "!",
        }.get(lead.management_status.value, " ")

        owner = (lead.owner_name.value if lead.owner_name else
                 lead.owner_entity.value if lead.owner_entity else "—")
        print(
            f"[{status_icon}] {lead.full_address} | "
            f"units={lead.units_estimated or '?'} | "
            f"owner={owner}"
        )

    print(f"\n{len(leads)} lead(s) shown")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    if not args.db.exists():
        print(f"Database not found: {args.db}")
        return 1

    from .exports.database import LeadDatabase
    db = LeadDatabase(args.db)
    total = db.count()
    owner = db.count(management_status="likely_owner_managed")
    third = db.count(management_status="likely_third_party")
    unclear = db.count(management_status="unclear")
    review = db.count(manual_review_only=True)
    db.close()

    print(f"\nLead Database Statistics")
    print(f"  Total leads:           {total}")
    print(f"  Likely owner-managed:  {owner}")
    print(f"  Likely third-party:    {third}")
    print(f"  Unclear:               {unclear}")
    print(f"  Flagged for review:    {review}")
    print()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "query":
        return cmd_query(args)
    elif args.command == "stats":
        return cmd_stats(args)
    else:
        parse_args(["--help"])
        return 0


if __name__ == "__main__":
    sys.exit(main())
