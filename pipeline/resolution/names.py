"""Shared name-matching primitives for cross-source resolution.

Normalization + distinctive-token extraction + a fuzzy name score, used when
bridging entities across sources that share no deterministic key (SEC CIK/EIN vs
FCC FRN are disjoint namespaces — handoff 2026-09-18). This is the "Likely"
side of the trust model (design/entity-discovery.md): every score here is a
probabilistic inference graded high/med/low, never "official".

The distinctive-token guard is the load-bearing false-positive killer: WRatio
alone scored unrelated "GANNETT CO INC" at 85 against "FOX TELEVISION STATIONS".
Requiring shared *distinctive* tokens (identity words, not domain filler) rejects
that pair (zero overlap) while keeping true matches.

NOTE (dedup TODO): pipeline/discovery/cross_source_overlap.py carries a
near-identical normalize()/distinctive_tokens(). This module is the intended
canonical home (data-model.md: resolution/ = shared utils); fold discovery's
copy into this one when convenient.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz, utils

# Legal-form suffixes stripped before comparison (order-independent, applied to
# convergence so "FOO CO INC" -> "FOO"). Mirrors discovery's proven list.
_SUFFIX_PATTERNS = [
    r",?\s+LLC\.?$", r",?\s+L\.L\.C\.?$", r",?\s+INC\.?$", r",?\s+INCORPORATED$",
    r",?\s+CORP\.?$", r",?\s+CORPORATION$", r",?\s+LTD\.?$", r",?\s+LIMITED$",
    r",?\s+L\.P\.?$", r",?\s+LP$", r",?\s+CO\.?$", r",?\s+DEBTOR-IN-POSSESSION$",
]
_SUFFIX_RE = re.compile("|".join(_SUFFIX_PATTERNS), re.IGNORECASE)

# EDGAR appends a state-of-incorporation marker like " /DE/" to company names.
_EDGAR_STATE_RE = re.compile(r"\s*/[A-Z]{2}/\s*$")

# Industry/filler words that do NOT carry identity — excluded from distinctive tokens.
DOMAIN_WORDS = frozenset({
    "BROADCASTING", "BROADCAST", "COMMUNICATIONS", "COMMUNICATION",
    "MEDIA", "TELEVISION", "TV", "RADIO", "ENTERTAINMENT",
    "HOLDINGS", "GROUP", "COMPANY", "ENTERPRISES", "NETWORKS",
    "NETWORK", "LICENSEE", "LICENSE", "STATIONS", "PARTNERS",
})


def normalize(name: str) -> str:
    """Uppercase, strip 'THE ', EDGAR /XX/ marker, and legal-form suffixes."""
    n = (name or "").upper().strip()
    if n.startswith("THE "):
        n = n[4:]
    n = _EDGAR_STATE_RE.sub("", n).strip()
    prev = None
    while n != prev:  # loop: peel stacked suffixes ("... CO INC")
        prev = n
        n = _SUFFIX_RE.sub("", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def distinctive_tokens(name: str) -> set[str]:
    """Identity-bearing tokens of a name: normalize, drop domain filler + 1-char."""
    return {t for t in normalize(name).split() if t not in DOMAIN_WORDS and len(t) > 1}


def name_score(a: str, b: str) -> float:
    """WRatio (0-100) on the normalized names. rapidfuzz default_process lowers/strips."""
    return float(fuzz.WRatio(normalize(a), normalize(b), processor=utils.default_process))
