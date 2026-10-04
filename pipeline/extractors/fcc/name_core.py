"""Company-name normalization + distinctive-token extraction.

Mirrors `pipeline/discovery/cross_source_overlap.py` (D3) EXACTLY — same
SUFFIX patterns, DOMAIN_WORDS, and token rule. That parity is load-bearing:
the FCC extractor uses `distinctive_tokens` to decide which names under an FRN
are genuine aliases vs counterparties, and the SEC<->FCC fuzzy merge (tile 4)
uses the same function to decide identity. If the two definitions drift, a name
the extractor treats as merge-safe could still poison the merge.

TODO (coordinate, don't do unilaterally): unify this + D3's copy into the
shared `pipeline/resolution/names.py` (architectural home per data-model.md),
so extractor alias-gating and tile-4 merge provably share one definition.
"""
from __future__ import annotations

import re

SUFFIX_PATTERNS = [
    r",?\s+LLC\.?$",
    r",?\s+L\.L\.C\.?$",
    r",?\s+INC\.?$",
    r",?\s+INCORPORATED$",
    r",?\s+CORP\.?$",
    r",?\s+CORPORATION$",
    r",?\s+LTD\.?$",
    r",?\s+LIMITED$",
    r",?\s+L\.P\.?$",
    r",?\s+LP$",
    r",?\s+CO\.?$",
    r",?\s+DEBTOR-IN-POSSESSION$",
]
SUFFIX_RE = re.compile("|".join(SUFFIX_PATTERNS), re.IGNORECASE)

DOMAIN_WORDS = frozenset({
    "BROADCASTING", "BROADCAST", "COMMUNICATIONS", "COMMUNICATION",
    "MEDIA", "TELEVISION", "TV", "RADIO", "ENTERTAINMENT",
    "HOLDINGS", "GROUP", "COMPANY", "ENTERPRISES", "NETWORKS",
    "NETWORK", "LICENSEE", "LICENSE", "STATIONS", "PARTNERS",
})


def normalize(name: str) -> str:
    n = (name or "").upper().strip()
    if n.startswith("THE "):
        n = n[4:]
    prev = None
    while n != prev:  # strip stacked suffixes, e.g. "..., INC. CO."
        prev = n
        n = SUFFIX_RE.sub("", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def distinctive_tokens(name: str) -> set[str]:
    """Identity-bearing tokens of a name: normalized, minus generic domain words."""
    return {t for t in normalize(name).split() if t not in DOMAIN_WORDS and len(t) > 1}
