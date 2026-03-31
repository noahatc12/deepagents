"""
Address normalization utilities.

Normalizes free-form address strings into structured components and
produces a canonical string for deduplication.
"""

import re
import unicodedata
from typing import Optional


# Common abbreviation maps (USPS-style)
STREET_SUFFIX_MAP: dict[str, str] = {
    "avenue": "ave",
    "boulevard": "blvd",
    "circle": "cir",
    "court": "ct",
    "drive": "dr",
    "expressway": "expy",
    "freeway": "fwy",
    "highway": "hwy",
    "lane": "ln",
    "parkway": "pkwy",
    "place": "pl",
    "road": "rd",
    "square": "sq",
    "street": "st",
    "terrace": "ter",
    "trail": "trl",
    "way": "way",
}

DIRECTION_MAP: dict[str, str] = {
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "northeast": "ne",
    "northwest": "nw",
    "southeast": "se",
    "southwest": "sw",
}

UNIT_PREFIXES = {"apt", "apartment", "unit", "suite", "ste", "floor", "fl", "#"}

STATE_ABBREV: dict[str, str] = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
    "california": "ca", "colorado": "co", "connecticut": "ct", "delaware": "de",
    "florida": "fl", "georgia": "ga", "hawaii": "hi", "idaho": "id",
    "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
    "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv",
    "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm", "new york": "ny",
    "north carolina": "nc", "north dakota": "nd", "ohio": "oh", "oklahoma": "ok",
    "oregon": "or", "pennsylvania": "pa", "rhode island": "ri", "south carolina": "sc",
    "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut",
    "vermont": "vt", "virginia": "va", "washington": "wa", "west virginia": "wv",
    "wisconsin": "wi", "wyoming": "wy",
}


def _unicode_normalize(text: str) -> str:
    """Strip accents and normalize unicode."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_address(raw: str) -> str:
    """
    Return a canonical, lowercase, punctuation-stripped address string
    suitable for deduplication hashing.

    This is intentionally lossy – unit numbers are stripped for
    building-level dedup, use `normalize_address_full` if you need them.
    """
    if not raw:
        return ""

    text = _unicode_normalize(raw).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = text.split()

    normalized: list[str] = []
    skip_next = False
    for i, tok in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        # Drop unit prefixes and the token following them
        if tok in UNIT_PREFIXES:
            skip_next = True
            continue
        # Abbreviate street suffixes
        tok = STREET_SUFFIX_MAP.get(tok, tok)
        # Abbreviate directions
        tok = DIRECTION_MAP.get(tok, tok)
        normalized.append(tok)

    return " ".join(normalized).strip()


def normalize_address_full(raw: str) -> str:
    """
    Like normalize_address but preserves unit information.
    """
    if not raw:
        return ""
    text = _unicode_normalize(raw).lower()
    text = re.sub(r"[^\w\s#]", " ", text)
    tokens = text.split()
    normalized = [
        DIRECTION_MAP.get(STREET_SUFFIX_MAP.get(tok, tok), STREET_SUFFIX_MAP.get(tok, tok))
        for tok in tokens
    ]
    return " ".join(normalized).strip()


def normalize_state(state: str) -> str:
    """Return 2-letter state abbreviation (lowercase)."""
    s = state.strip().lower()
    if len(s) == 2:
        return s
    return STATE_ABBREV.get(s, s)


def normalize_zip(zip_code: str) -> str:
    """Extract 5-digit ZIP from free text."""
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", zip_code or "")
    return match.group(1) if match else ""


def normalize_phone(phone: str) -> str:
    """Strip to digits; return E.164-ish 10-digit US number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else phone.strip()


def address_fingerprint(street: str, city: str, state: str, zip_code: str) -> str:
    """
    Produce a stable fingerprint for deduplication.
    Two records with the same fingerprint refer to the same building.
    """
    parts = [
        normalize_address(street),
        city.strip().lower(),
        normalize_state(state),
        normalize_zip(zip_code),
    ]
    return "|".join(parts)


def parse_address_line(line: str) -> dict[str, str]:
    """
    Best-effort parse of a single-line address into components.
    Returns keys: street, city, state, zip.

    Example:
        "123 Main St, Oakland, CA 94601" ->
        {"street": "123 main st", "city": "oakland", "state": "ca", "zip": "94601"}
    """
    result = {"street": "", "city": "", "state": "", "zip": ""}
    if not line:
        return result

    # Try to extract ZIP first
    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", line)
    if zip_match:
        result["zip"] = zip_match.group(1)
        line = line[: zip_match.start()] + line[zip_match.end() :]

    # Try to extract state (2-letter abbreviation before ZIP or at end)
    state_match = re.search(r"\b([A-Za-z]{2})\s*$", line.strip())
    if state_match:
        result["state"] = state_match.group(1).lower()
        line = line[: state_match.start()].strip()

    # Split on commas
    parts = [p.strip() for p in line.split(",") if p.strip()]
    if len(parts) >= 2:
        result["street"] = parts[0].lower()
        result["city"] = parts[-1].lower()
    elif len(parts) == 1:
        result["street"] = parts[0].lower()

    return result
