"""
Entity name normalization helpers.
"""

import re


# Common entity suffixes
ENTITY_SUFFIX_RE = re.compile(
    r"\b(llc|lp|ltd|inc|corp|co|partnership|trust|properties|"
    r"investments|realty|real estate|holdings|group|enterprises|"
    r"associates|management|mgmt|pm|apts|apartments)\b",
    re.IGNORECASE,
)


def normalize_entity_name(name: str) -> str:
    """
    Lowercase, strip punctuation, collapse whitespace.
    Returns a canonical form for deduplication.
    """
    if not name:
        return ""
    text = name.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def entity_fingerprint(name: str) -> str:
    """Remove common suffixes for fuzzy entity matching."""
    n = normalize_entity_name(name)
    n = ENTITY_SUFFIX_RE.sub("", n)
    return re.sub(r"\s+", " ", n).strip()


KNOWN_MANAGEMENT_COMPANIES: set[str] = {
    # National / large regional
    "greystar",
    "aimco",
    "camden property trust",
    "equity residential",
    "avalonbay",
    "essex property trust",
    "udr",
    "nrp group",
    "related companies",
    "lion real estate",
    "kettler",
    "bell partners",
    "alliance residential",
    "mark taylor",
    "first service residential",
    "firstservice residential",
    "cushman wakefield",
    "jll",
    "cbre",
    "colliers",
    "lincoln property company",
    "lincoln property",
    "morgan properties",
    "RPM living",
    "weidner apartment homes",
    "rangewater",
    "cortland",
    "pinnacle property management",
    "pinnacle",
    # California / West Coast regional
    "prometheus real estate",
    "prometheus",
    "spieker properties",
    "equity apartments",
    "wood partners",
    "irvine company",
    "bentall greenoak",
    "castle green",
    "sequoia equities",
    "sares regis",
    "cirque",
    "prometheus",
    "bc wood",
    "waterford property company",
    "carmel partners",
    "pdt",
    # Property management brands (not ownership)
    "appfolio",
    "buildium",
    "real page",
    "yardi",
}


def is_known_management_company(name: str) -> bool:
    """Return True if name matches a known third-party PM company."""
    fp = entity_fingerprint(name)
    for known in KNOWN_MANAGEMENT_COMPANIES:
        if known in fp or fp in known:
            return True
    return False
