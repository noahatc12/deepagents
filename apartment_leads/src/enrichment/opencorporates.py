"""
OpenCorporates Enricher

OpenCorporates provides an API for public company data.
Free tier allows a limited number of requests per day.

API docs: https://api.opencorporates.com/
Terms:    https://opencorporates.com/info/api_terms

This enricher uses the company search endpoint to look up owner entities.
An API key is optional for the free tier but increases rate limits.

Usage:
    Set OPENCORPORATES_API_KEY in .env for higher rate limits.
    Leave unset for anonymous access (lower limits).
"""

from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlencode

from .base import BaseEnricher
from ..models import PropertyLead
from ..utils.rate_limiter import with_retry
from ..utils.logging import get_logger

logger = get_logger(__name__)

OPENCORP_BASE = "https://api.opencorporates.com/v0.4"
OPENCORP_SEARCH = f"{OPENCORP_BASE}/companies/search"


class OpenCorporatesEnricher(BaseEnricher):
    """
    Enriches owner entities with OpenCorporates public company data.

    Config keys:
        api_key (str, optional): OpenCorporates API key.
        jurisdiction_code (str, optional): E.g. "us_ca" for California.
    """

    enricher_name = "opencorporates"

    @with_retry(max_attempts=3, base_delay=2.0)
    def _search_company(self, name: str, jurisdiction: Optional[str] = None) -> Optional[dict]:
        if not self._session:
            return None

        params: dict = {"q": name, "format": "json"}
        if jurisdiction:
            params["jurisdiction_code"] = jurisdiction
        api_key = self._config.get("api_key")
        if api_key:
            params["api_token"] = api_key

        try:
            text = self._session.get(OPENCORP_SEARCH, params=params)
            data = json.loads(text)
            companies = data.get("results", {}).get("companies", [])
            if companies:
                return companies[0].get("company", {})
        except PermissionError as exc:
            self._logger.debug("robots.txt blocked: %s", exc)
        except Exception as exc:
            self._logger.warning("OpenCorporates search failed: %s", exc)

        return None

    def enrich(self, lead: PropertyLead) -> PropertyLead:
        entity_name = lead.owner_entity.value if lead.owner_entity else None
        if not entity_name:
            return lead

        jurisdiction = self._config.get("jurisdiction_code", "us_ca")
        company = self._search_company(entity_name, jurisdiction)
        if not company:
            return lead

        source_url = company.get("opencorporates_url", OPENCORP_SEARCH)

        # Registered agent
        agent = company.get("registered_agent_name")
        lead.owner_contact_name = self._set_if_better(
            lead.owner_contact_name,
            agent,
            source=self.enricher_name,
            source_url=source_url,
            confidence=0.55,
        )

        # Registered address
        reg_addr = company.get("registered_address_in_full")
        lead.mailing_address = self._set_if_better(
            lead.mailing_address,
            reg_addr,
            source=self.enricher_name,
            source_url=source_url,
            confidence=0.5,
        )

        # Confirm / improve entity name
        corp_name = company.get("name")
        if corp_name and lead.owner_entity:
            lead.owner_entity = self._set_if_better(
                lead.owner_entity,
                corp_name,
                source=self.enricher_name,
                source_url=source_url,
                confidence=0.8,
            )

        lead.source_urls = list(dict.fromkeys(lead.source_urls + [source_url]))
        lead.source_names = list(dict.fromkeys(lead.source_names + [self.enricher_name]))
        return lead
