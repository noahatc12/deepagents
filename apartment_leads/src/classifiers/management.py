"""
Management Status Classifier

Determines whether a property is likely:
  - third-party managed
  - owner-managed
  - unclear

The classifier is rule-based and works in two phases:

Phase 1 – Signal extraction:
    Collect signals from all available data: website content,
    management name fields, entity names, listing data.

Phase 2 – Scoring:
    Each signal has a weight. Signals for "third-party" raise the
    third-party score; signals for "owner-managed" raise that score.
    The dominant score determines the classification.

An LLM review interface is provided for the "unclear" bucket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Protocol

from ..models import ConfidenceLevel, ManagementStatus, PropertyLead
from ..utils.entity import is_known_management_company, normalize_entity_name
from ..utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Signal definitions
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    name: str
    description: str
    weight: float          # Positive = third-party evidence; Negative = owner-managed


THIRD_PARTY_SIGNALS: list[Signal] = [
    Signal("known_pm_company_name", "Management name matches known PM company", 0.9),
    Signal("managed_by_text", '"managed by" text found on website/listing', 0.7),
    Signal("management_company_branding", "Distinct management brand on website", 0.7),
    Signal("email_domain_mismatch", "Contact email domain differs from property domain", 0.5),
    Signal("leasing_office_pm_brand", "Leasing office contact references PM brand", 0.6),
    Signal("repeated_manager_entity", "Same manager entity across many properties", 0.8),
    Signal("pm_website_pattern", "Website URL matches known PM domain pattern", 0.8),
    Signal("greystar_signal", "Greystar-specific indicators", 1.0),
    Signal("management_footer", "PM company name in website footer", 0.65),
    Signal("realpage_yardi_signal", "RealPage/Yardi ILS listing", 0.4),
]

OWNER_MANAGED_SIGNALS: list[Signal] = [
    Signal("self_managed_text", '"self-managed" or "owner-managed" on listing', -0.8),
    Signal("owner_contact", "Owner name appears as direct contact", -0.6),
    Signal("sole_property_entity", "Owner entity name matches property name", -0.5),
    Signal("individual_person_name", "Owner appears to be individual (not LLC/Corp)", -0.4),
    Signal("no_management_field", "No management name found anywhere", -0.3),
    Signal("same_mailing_as_property", "Owner mailing address == property address", -0.5),
    Signal("onsite_managed_text", '"on-site" management text found', -0.5),
]


# ---------------------------------------------------------------------------
# Pattern lists (compiled for performance)
# ---------------------------------------------------------------------------

MANAGED_BY_RE = re.compile(
    r"\bmanaged\s+by\b|\bproperty\s+management\b|\bpm\b|\bproperty\s+manager\b",
    re.IGNORECASE,
)

SELF_MANAGED_RE = re.compile(
    r"\bself[- ]managed\b|\bowner[- ]managed\b|\bno\s+management\s+company\b",
    re.IGNORECASE,
)

ON_SITE_RE = re.compile(r"\bon[- ]site\s+manager\b|\bon[- ]site\s+management\b", re.IGNORECASE)

PM_WEBSITE_DOMAINS = {
    "greystar.com", "aimco.com", "camdenliving.com", "equityapartments.com",
    "avalonbay.com", "udr.com", "lincolnapts.com", "morganproperties.com",
    "pinnacleliving.com", "cortland.com", "weidner.com", "firstserviceresidential.com",
    "jll.com", "cushmanwakefield.com", "cbre.com", "colliers.com",
    "prometheusapartments.com", "sares-regis.com",
}

INDIVIDUAL_NAME_RE = re.compile(
    r"^(mr\.?|ms\.?|mrs\.?|dr\.?)?\s*[A-Z][a-z]+ [A-Z][a-z]+$"
)

LLC_CORP_RE = re.compile(
    r"\b(llc|lp|ltd|inc|corp|co\.?|trust|partnership|properties|holdings|realty)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    status: ManagementStatus
    confidence: float
    confidence_level: ConfidenceLevel
    signals_fired: list[str] = field(default_factory=list)
    detected_company: Optional[str] = None
    needs_review: bool = False


class ManagementClassifier:
    """
    Rule-based management status classifier.

    Usage:
        clf = ManagementClassifier()
        result = clf.classify(lead)
        lead.management_status = result.status
    """

    def __init__(self, unclear_threshold: float = 0.2) -> None:
        self._unclear_threshold = unclear_threshold

    def classify(self, lead: PropertyLead) -> ClassificationResult:
        """Classify a single lead and return a ClassificationResult."""
        score = 0.0
        signals: list[str] = []
        detected_company: Optional[str] = None

        # --- Collect text to analyze ---
        texts = []
        if lead.property_name:
            texts.append(lead.property_name)
        if lead.website:
            texts.append(lead.website)
        if lead.detected_management_company:
            texts.append(lead.detected_management_company)

        owner_entity = lead.owner_entity.value if lead.owner_entity else None
        owner_name = lead.owner_name.value if lead.owner_name else None

        # Combine management name from source records
        mgmt_name = None  # Populated by collectors / normalizer if available
        for note in lead.notes.split(";"):
            if "management_name:" in note:
                mgmt_name = note.split("management_name:")[-1].strip()
                break

        combined_text = " ".join(texts)

        # --- Apply signals ---

        # 1. Known PM company name
        if mgmt_name and is_known_management_company(mgmt_name):
            score += THIRD_PARTY_SIGNALS[0].weight
            signals.append("known_pm_company_name")
            detected_company = mgmt_name

        # 2. "managed by" text
        if MANAGED_BY_RE.search(combined_text):
            score += THIRD_PARTY_SIGNALS[1].weight
            signals.append("managed_by_text")

        # 3. Website domain matches known PM
        if lead.website:
            domain = self._extract_domain(lead.website)
            if domain in PM_WEBSITE_DOMAINS:
                score += THIRD_PARTY_SIGNALS[4].weight
                signals.append("pm_website_pattern")
                detected_company = detected_company or domain

        # 4. Owner entity is a known PM company
        if owner_entity and is_known_management_company(owner_entity):
            score += THIRD_PARTY_SIGNALS[0].weight
            signals.append("known_pm_company_name")
            detected_company = detected_company or owner_entity

        # 5. Self-managed text
        if SELF_MANAGED_RE.search(combined_text):
            score += OWNER_MANAGED_SIGNALS[0].weight
            signals.append("self_managed_text")

        # 6. On-site management text
        if ON_SITE_RE.search(combined_text):
            score += OWNER_MANAGED_SIGNALS[6].weight
            signals.append("onsite_managed_text")

        # 7. No management name found
        if not mgmt_name and not detected_company:
            score += OWNER_MANAGED_SIGNALS[4].weight
            signals.append("no_management_field")

        # 8. Owner is an individual (not a company)
        if owner_name and not LLC_CORP_RE.search(owner_name):
            if INDIVIDUAL_NAME_RE.match(owner_name):
                score += OWNER_MANAGED_SIGNALS[3].weight
                signals.append("individual_person_name")

        # 9. Owner mailing address == property address
        if lead.mailing_address and lead.mailing_address.value:
            from ..utils.address import address_fingerprint, normalize_address
            prop_fp = address_fingerprint(
                lead.street_address, lead.city, lead.state, lead.zip_code
            )
            mail_fp = address_fingerprint(
                lead.mailing_address.value, lead.city, lead.state, lead.zip_code
            )
            if prop_fp and mail_fp and prop_fp == mail_fp:
                score += OWNER_MANAGED_SIGNALS[5].weight
                signals.append("same_mailing_as_property")

        # --- Map score to status ---
        abs_score = abs(score)
        threshold = self._unclear_threshold

        if abs_score < threshold:
            status = ManagementStatus.UNCLEAR
            confidence = abs_score / threshold if threshold else 0.0
            needs_review = True
        elif score > 0:
            status = ManagementStatus.LIKELY_THIRD_PARTY
            confidence = min(1.0, abs_score)
            needs_review = False
        else:
            status = ManagementStatus.LIKELY_OWNER_MANAGED
            confidence = min(1.0, abs_score)
            needs_review = abs_score < 0.5

        # Cap confidence at 1.0
        confidence = round(min(1.0, max(0.0, confidence)), 3)
        confidence_level = self._to_level(confidence)

        return ClassificationResult(
            status=status,
            confidence=confidence,
            confidence_level=confidence_level,
            signals_fired=signals,
            detected_company=detected_company,
            needs_review=needs_review,
        )

    @staticmethod
    def _extract_domain(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc.lower().lstrip("www.")
        except Exception:
            return ""

    @staticmethod
    def _to_level(confidence: float) -> ConfidenceLevel:
        if confidence >= 0.80:
            return ConfidenceLevel.HIGH
        if confidence >= 0.50:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW


def classify_leads(
    leads: list[PropertyLead],
    classifier: Optional[ManagementClassifier] = None,
) -> list[PropertyLead]:
    """Classify a list of leads in-place and return them."""
    clf = classifier or ManagementClassifier()
    for lead in leads:
        result = clf.classify(lead)
        lead.management_status = result.status
        lead.management_status_confidence = result.confidence
        lead.management_status_confidence_level = result.confidence_level
        lead.management_signals = result.signals_fired
        if result.detected_company:
            lead.detected_management_company = result.detected_company
        if result.needs_review:
            lead.manual_review_flag = True
            lead.review_reason = (
                lead.review_reason or "Low-confidence management classification"
            )
    return leads


# ---------------------------------------------------------------------------
# LLM Review Interface (optional, activated for unclear cases)
# ---------------------------------------------------------------------------

class LLMReviewerProtocol(Protocol):
    """
    Interface for an optional LLM-assisted review step.

    Implement this protocol and pass an instance to llm_review_leads()
    to enable AI-assisted classification of ambiguous cases.

    Example implementation (OpenAI):
        class OpenAIReviewer:
            def review(self, lead: PropertyLead, context: str) -> ClassificationResult:
                prompt = f"Given this apartment property data:\\n{context}\\n..."
                response = openai.chat.completions.create(...)
                ...
    """

    def review(self, lead: PropertyLead, context: str) -> ClassificationResult:
        ...


def llm_review_leads(
    leads: list[PropertyLead],
    reviewer: LLMReviewerProtocol,
) -> list[PropertyLead]:
    """
    Run an LLM reviewer on leads flagged for manual review.
    Updates management_status and confidence in-place.
    """
    unclear = [l for l in leads if l.management_status == ManagementStatus.UNCLEAR]
    logger.info("Sending %d unclear leads to LLM reviewer", len(unclear))

    for lead in unclear:
        context = _build_review_context(lead)
        try:
            result = reviewer.review(lead, context)
            lead.management_status = result.status
            lead.management_status_confidence = result.confidence
            lead.management_status_confidence_level = result.confidence_level
            lead.management_signals.extend(result.signals_fired)
            lead.notes += " [LLM reviewed]"
        except Exception as exc:
            logger.warning("LLM review failed for %s: %s", lead.full_address, exc)

    return leads


def _build_review_context(lead: PropertyLead) -> str:
    lines = [
        f"Property: {lead.property_name or 'Unknown'}",
        f"Address: {lead.full_address}",
        f"Units: {lead.units_estimated or 'unknown'}",
        f"Website: {lead.website or 'none'}",
        f"Owner name: {lead.owner_name.value if lead.owner_name else 'unknown'}",
        f"Owner entity: {lead.owner_entity.value if lead.owner_entity else 'unknown'}",
        f"Mailing address: {lead.mailing_address.value if lead.mailing_address else 'unknown'}",
        f"Signals fired: {', '.join(lead.management_signals) or 'none'}",
        f"Notes: {lead.notes or 'none'}",
    ]
    return "\n".join(lines)
