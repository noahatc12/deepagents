"""
CSV and Excel export module.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from ..models import PropertyLead
from ..utils.logging import get_logger

logger = get_logger(__name__)

FIELD_ORDER = [
    "property_name", "street_address", "city", "state", "zip", "county", "apn",
    "units_estimated", "year_built", "website", "phone",
    "management_status", "management_status_confidence",
    "detected_management_company", "management_signals",
    "owner_name", "owner_entity", "owner_contact_name",
    "owner_email", "owner_phone", "mailing_address",
    "owner_name_confidence", "owner_entity_confidence",
    "source_urls", "source_names",
    "manual_review_flag", "review_reason", "notes", "created_at",
]


def export_csv(
    leads: list[PropertyLead],
    output_path: Path,
    review_only: bool = False,
) -> Path:
    """
    Export leads to CSV.

    Args:
        leads:       List of PropertyLead objects.
        output_path: Output file path.
        review_only: If True, only export leads flagged for manual review.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [l.to_flat_dict() for l in leads]
    if review_only:
        rows = [r for r in rows if r.get("manual_review_flag")]

    logger.info("Exporting %d leads to CSV: %s", len(rows), output_path)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELD_ORDER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def export_excel(
    leads: list[PropertyLead],
    output_path: Path,
    review_only: bool = False,
) -> Path:
    """Export leads to Excel (.xlsx)."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        logger.error(
            "openpyxl not installed. Run: pip install openpyxl. Falling back to CSV."
        )
        csv_path = output_path.with_suffix(".csv")
        return export_csv(leads, csv_path, review_only=review_only)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [l.to_flat_dict() for l in leads]
    if review_only:
        rows = [r for r in rows if r.get("manual_review_flag")]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Apartment Leads"

    # Header row
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for col_idx, field in enumerate(FIELD_ORDER, start=1):
        cell = ws.cell(row=1, column=col_idx, value=field.replace("_", " ").title())
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Data rows – highlight review rows
    review_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    for row_idx, row in enumerate(rows, start=2):
        for col_idx, field in enumerate(FIELD_ORDER, start=1):
            val = row.get(field, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=str(val) if val is not None else "")
            if row.get("manual_review_flag"):
                cell.fill = review_fill

    # Auto-size columns (approximate)
    for col_idx in range(1, len(FIELD_ORDER) + 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 18

    # Freeze header
    ws.freeze_panes = "A2"

    wb.save(output_path)
    logger.info("Exported %d leads to Excel: %s", len(rows), output_path)
    return output_path


def export_json(leads: list[PropertyLead], output_path: Path) -> Path:
    """Export leads to JSON (full flat dict per record)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [l.to_flat_dict() for l in leads]
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, default=str)
    logger.info("Exported %d leads to JSON: %s", len(records), output_path)
    return output_path


def export_review_queue(leads: list[PropertyLead], output_path: Path) -> Path:
    """
    Export only leads flagged for manual review to a separate CSV.
    Useful for routing to a human reviewer or CRM queue.
    """
    return export_csv(leads, output_path, review_only=True)
