"""
SQLite database export / persistence module.

Provides:
  - LeadDatabase: SQLite-backed store for PropertyLead objects
  - Supports upsert (re-runs merge with existing data)
  - Supports querying by management_status, city, etc.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from ..models import (
    ConfidenceLevel,
    EnrichedField,
    ManagementStatus,
    PropertyLead,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id                              TEXT PRIMARY KEY,
    created_at                      TEXT,
    updated_at                      TEXT,
    property_name                   TEXT,
    street_address                  TEXT,
    city                            TEXT,
    state                           TEXT,
    zip_code                        TEXT,
    county                          TEXT,
    apn                             TEXT,
    units_estimated                 INTEGER,
    year_built                      INTEGER,
    website                         TEXT,
    phone                           TEXT,
    management_status               TEXT,
    management_status_confidence    REAL,
    management_status_confidence_level TEXT,
    detected_management_company     TEXT,
    management_signals              TEXT,   -- JSON array
    owner_name_value                TEXT,
    owner_name_source               TEXT,
    owner_name_confidence           REAL,
    owner_entity_value              TEXT,
    owner_entity_source             TEXT,
    owner_entity_confidence         REAL,
    owner_contact_name_value        TEXT,
    owner_email_value               TEXT,
    owner_phone_value               TEXT,
    mailing_address_value           TEXT,
    mailing_address_source          TEXT,
    source_ids                      TEXT,   -- JSON array
    source_urls                     TEXT,   -- JSON array
    source_names                    TEXT,   -- JSON array
    manual_review_flag              INTEGER,
    review_reason                   TEXT,
    notes                           TEXT
);

CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(management_status);
CREATE INDEX IF NOT EXISTS idx_leads_zip ON leads(zip_code);
CREATE INDEX IF NOT EXISTS idx_leads_review ON leads(manual_review_flag);
"""


def _ef_val(ef: Optional[EnrichedField]) -> Optional[str]:
    return ef.value if ef else None

def _ef_src(ef: Optional[EnrichedField]) -> Optional[str]:
    return ef.source if ef else None

def _ef_conf(ef: Optional[EnrichedField]) -> float:
    return ef.confidence if ef else 0.0


class LeadDatabase:
    """
    SQLite-backed storage for PropertyLead objects.

    Usage:
        db = LeadDatabase(Path("data/leads.db"))
        db.upsert_leads(leads)
        for lead in db.query(management_status="likely_owner_managed"):
            print(lead.full_address)
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        logger.info("Database initialized: %s", db_path)

    def _init_db(self) -> None:
        self._conn.executescript(CREATE_TABLE_SQL)
        self._conn.commit()

    def upsert_leads(self, leads: list[PropertyLead]) -> int:
        """Insert or replace leads. Returns count of rows affected."""
        now = datetime.utcnow().isoformat()
        rows = []
        for lead in leads:
            rows.append((
                lead.id,
                lead.created_at.isoformat(),
                now,
                lead.property_name,
                lead.street_address,
                lead.city,
                lead.state,
                lead.zip_code,
                lead.county,
                lead.apn,
                lead.units_estimated,
                lead.year_built,
                lead.website,
                lead.phone,
                lead.management_status.value,
                lead.management_status_confidence,
                lead.management_status_confidence_level.value,
                lead.detected_management_company,
                json.dumps(lead.management_signals),
                _ef_val(lead.owner_name),
                _ef_src(lead.owner_name),
                _ef_conf(lead.owner_name),
                _ef_val(lead.owner_entity),
                _ef_src(lead.owner_entity),
                _ef_conf(lead.owner_entity),
                _ef_val(lead.owner_contact_name),
                _ef_val(lead.owner_email),
                _ef_val(lead.owner_phone),
                _ef_val(lead.mailing_address),
                _ef_src(lead.mailing_address),
                json.dumps(lead.source_ids),
                json.dumps(lead.source_urls),
                json.dumps(lead.source_names),
                int(lead.manual_review_flag),
                lead.review_reason,
                lead.notes,
            ))

        self._conn.executemany(
            """
            INSERT OR REPLACE INTO leads VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,
            rows,
        )
        self._conn.commit()
        logger.info("Upserted %d leads into database", len(rows))
        return len(rows)

    def query(
        self,
        management_status: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        manual_review_only: bool = False,
        limit: Optional[int] = None,
    ) -> Iterator[PropertyLead]:
        """Query leads with optional filters. Yields PropertyLead objects."""
        conditions: list[str] = []
        params: list = []

        if management_status:
            conditions.append("management_status = ?")
            params.append(management_status)
        if city:
            conditions.append("lower(city) = lower(?)")
            params.append(city)
        if state:
            conditions.append("upper(state) = upper(?)")
            params.append(state)
        if zip_code:
            conditions.append("zip_code = ?")
            params.append(zip_code)
        if manual_review_only:
            conditions.append("manual_review_flag = 1")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        sql = f"SELECT * FROM leads {where} ORDER BY city, street_address {limit_clause}"
        for row in self._conn.execute(sql, params):
            yield self._row_to_lead(dict(row))

    def count(self, **filters) -> int:
        """Return count of leads matching filters."""
        return sum(1 for _ in self.query(**filters))

    def _row_to_lead(self, row: dict) -> PropertyLead:
        def _ef(val_key, src_key, conf_key, url="") -> Optional[EnrichedField]:
            v = row.get(val_key)
            if not v:
                return None
            return EnrichedField(
                value=v,
                source=row.get(src_key, ""),
                source_url=url,
                confidence=row.get(conf_key, 0.0) or 0.0,
            )

        return PropertyLead(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            property_name=row.get("property_name"),
            street_address=row.get("street_address", ""),
            city=row.get("city", ""),
            state=row.get("state", ""),
            zip_code=row.get("zip_code", ""),
            county=row.get("county", ""),
            apn=row.get("apn"),
            units_estimated=row.get("units_estimated"),
            year_built=row.get("year_built"),
            website=row.get("website"),
            phone=row.get("phone"),
            management_status=ManagementStatus(row.get("management_status", "unclear")),
            management_status_confidence=row.get("management_status_confidence", 0.0),
            management_status_confidence_level=ConfidenceLevel(
                row.get("management_status_confidence_level", "low")
            ),
            detected_management_company=row.get("detected_management_company"),
            management_signals=json.loads(row.get("management_signals") or "[]"),
            owner_name=_ef("owner_name_value", "owner_name_source", "owner_name_confidence"),
            owner_entity=_ef("owner_entity_value", "owner_entity_source", "owner_entity_confidence"),
            owner_contact_name=_ef("owner_contact_name_value", "", 0.0),
            owner_email=_ef("owner_email_value", "", 0.0),
            owner_phone=_ef("owner_phone_value", "", 0.0),
            mailing_address=_ef("mailing_address_value", "mailing_address_source", 0.0),
            source_ids=json.loads(row.get("source_ids") or "[]"),
            source_urls=json.loads(row.get("source_urls") or "[]"),
            source_names=json.loads(row.get("source_names") or "[]"),
            manual_review_flag=bool(row.get("manual_review_flag", 0)),
            review_reason=row.get("review_reason"),
            notes=row.get("notes", ""),
        )

    def close(self) -> None:
        self._conn.close()
