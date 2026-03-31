"""
Website content parser for management signal extraction.

Analyzes a property website's HTML to detect management company signals:
  - "managed by" text
  - PM company branding in header/footer
  - Leasing contact pages
  - Email domain mismatches

Used by the enrichment pipeline before classification when a website URL
is available and accessible.

Compliance:
  - Only fetches URLs that pass the PoliteSession robots.txt check
  - Rate-limited via PoliteSession
"""

from __future__ import annotations

import re
from typing import Optional

from ..utils.entity import is_known_management_company, KNOWN_MANAGEMENT_COMPANIES
from ..utils.logging import get_logger

logger = get_logger(__name__)

MANAGED_BY_PATTERNS = [
    re.compile(r"managed\s+by\s+([\w\s&,.]+?)(?:\.|,|\n|<)", re.IGNORECASE),
    re.compile(r"property\s+management(?:\s+by)?\s*:?\s*([\w\s&,.]+?)(?:\.|,|\n|<)", re.IGNORECASE),
    re.compile(r"management\s+company\s*:?\s*([\w\s&,.]+?)(?:\.|,|\n|<)", re.IGNORECASE),
]

SELF_MANAGED_PATTERNS = [
    re.compile(r"self[- ]managed", re.IGNORECASE),
    re.compile(r"owner[- ]managed", re.IGNORECASE),
    re.compile(r"no\s+management\s+company", re.IGNORECASE),
    re.compile(r"on[- ]site\s+owner", re.IGNORECASE),
]

EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")


class WebsiteSignals:
    """Signals extracted from a property website."""

    def __init__(self) -> None:
        self.managed_by: Optional[str] = None
        self.is_self_managed: bool = False
        self.is_known_pm: bool = False
        self.email_domain: Optional[str] = None
        self.raw_text_snippet: str = ""


def extract_signals_from_html(html: str, property_domain: Optional[str] = None) -> WebsiteSignals:
    """
    Parse HTML content and return WebsiteSignals.

    Args:
        html:            Raw HTML string from the property website.
        property_domain: The domain of the property website itself,
                         used for email domain mismatch detection.
    """
    signals = WebsiteSignals()
    if not html:
        return signals

    # Strip HTML tags for text analysis
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    signals.raw_text_snippet = text[:500]

    # "managed by" patterns
    for pattern in MANAGED_BY_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip().rstrip(".,;")
            if len(candidate) > 3:
                signals.managed_by = candidate
                signals.is_known_pm = is_known_management_company(candidate)
                break

    # Self-managed patterns
    for pattern in SELF_MANAGED_PATTERNS:
        if pattern.search(text):
            signals.is_self_managed = True
            break

    # Email domain extraction
    email_match = EMAIL_RE.search(text)
    if email_match:
        signals.email_domain = email_match.group(1).lower()
        # Check if contact email domain differs from property domain
        if (
            property_domain
            and signals.email_domain
            and signals.email_domain != property_domain.lstrip("www.")
        ):
            logger.debug(
                "Email domain mismatch: contact=%s, property=%s",
                signals.email_domain,
                property_domain,
            )

    # Check for known PM company names anywhere in text
    if not signals.is_known_pm:
        text_lower = text.lower()
        for company in KNOWN_MANAGEMENT_COMPANIES:
            if company.lower() in text_lower:
                signals.is_known_pm = True
                signals.managed_by = signals.managed_by or company
                break

    return signals
