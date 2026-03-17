"""
California Secretary of State Business Entity Enricher

The CA SOS provides a public business entity search at:
  https://bizfileonline.sos.ca.gov/search/business

This enricher:
  1. Takes an owner_entity name from a lead
  2. Searches the CA SOS public search
  3. Attempts to find a registered agent or principal officer contact

Compliance notes:
  - CA SOS provides public business records – legal to access
  - bizfileonline.sos.ca.gov is the official state portal
  - Automated access is NOT clearly permitted via robots.txt as of 2024
    (the site uses anti-bot CAPTCHA for the web UI)
  - The CA SOS does provide a data file download program:
    https://www.sos.ca.gov/business-programs/business-entities/data-file-request
    (fee-based for bulk; free CSV available monthly for certain datasets)
  - This enricher uses the CSV bulk data approach when available,
    not the web UI, to avoid robots.txt issues.

TODO:
  - Implement CSV bulk download parser
  - Map entity name -> registered agent / officer contact
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Iterator, Optional

from .base import BaseEnricher
from ..models import PropertyLead
from ..utils.entity import normalize_entity_name, entity_fingerprint
from ..utils.logging import get_logger

logger = get_logger(__name__)

# CA SOS bulk data download landing page
CA_SOS_DATA_PAGE = "https://www.sos.ca.gov/business-programs/business-entities/data-file-request"


class CaSosEnricher(BaseEnricher):
    """
    Enrich owner entities with CA SOS business registration data.

    Config keys:
        ca_sos_csv_path (str): Path to downloaded CA SOS entity CSV file.
            Download from: https://www.sos.ca.gov/business-programs/business-entities/data-file-request
            Free monthly file available for active entities.

    When no CSV path is provided, this enricher logs a warning and skips.
    """

    enricher_name = "ca_sos"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        csv_path = self._config.get("ca_sos_csv_path")
        self._entity_index: dict[str, dict] = {}
        if csv_path:
            self._load_csv(Path(csv_path))
        else:
            self._logger.info(
                "CA SOS CSV not configured. "
                "Download from %s and set ca_sos_csv_path in config.",
                CA_SOS_DATA_PAGE,
            )

    def _load_csv(self, path: Path) -> None:
        """
        Load the CA SOS entity CSV file into an in-memory index.

        Expected columns (CA SOS format – may vary):
            Entity Name, Entity Number, Type, Status,
            Registration Date, Agent Name, Agent Address, ...

        TODO: Update column mapping once actual file format is confirmed.
        """
        if not path.exists():
            self._logger.warning("CA SOS CSV not found: %s", path)
            return

        self._logger.info("Loading CA SOS entity data from %s ...", path)
        count = 0
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                name_col = next(
                    (k for k in row if "name" in k.lower() and "entity" in k.lower()), None
                )
                if not name_col:
                    name_col = list(row.keys())[0] if row else None

                if name_col:
                    fp = entity_fingerprint(row.get(name_col, ""))
                    if fp:
                        self._entity_index[fp] = {k.lower(): v for k, v in row.items()}
                        count += 1

        self._logger.info("CA SOS: loaded %d entity records", count)

    def enrich(self, lead: PropertyLead) -> PropertyLead:
        if not self._entity_index:
            return lead

        entity_name = lead.owner_entity.value if lead.owner_entity else None
        if not entity_name:
            entity_name = lead.owner_name.value if lead.owner_name else None

        if not entity_name:
            return lead

        fp = entity_fingerprint(entity_name)
        row = self._entity_index.get(fp)

        if not row:
            # Try partial match
            for key, val in self._entity_index.items():
                if fp and (fp in key or key in fp):
                    row = val
                    break

        if not row:
            return lead

        # Extract registered agent name as a potential contact
        agent_name_key = next(
            (k for k in row if "agent" in k and "name" in k), None
        )
        agent_addr_key = next(
            (k for k in row if "agent" in k and "address" in k), None
        )

        if agent_name_key:
            lead.owner_contact_name = self._set_if_better(
                lead.owner_contact_name,
                row.get(agent_name_key, "").strip() or None,
                source=self.enricher_name,
                source_url=CA_SOS_DATA_PAGE,
                confidence=0.6,
            )

        if agent_addr_key:
            lead.mailing_address = self._set_if_better(
                lead.mailing_address,
                row.get(agent_addr_key, "").strip() or None,
                source=self.enricher_name,
                source_url=CA_SOS_DATA_PAGE,
                confidence=0.55,
            )

        # If entity not yet set, fill from SOS
        entity_col = next((k for k in row if "entity name" in k or k == "entity_name"), None)
        if entity_col and not lead.owner_entity:
            from ..models import EnrichedField
            from datetime import datetime
            lead.owner_entity = EnrichedField(
                value=row.get(entity_col, "").strip(),
                source=self.enricher_name,
                source_url=CA_SOS_DATA_PAGE,
                fetched_at=datetime.utcnow(),
                confidence=0.75,
            )

        lead.source_urls = list(dict.fromkeys(lead.source_urls + [CA_SOS_DATA_PAGE]))
        lead.source_names = list(dict.fromkeys(lead.source_names + [self.enricher_name]))
        return lead
