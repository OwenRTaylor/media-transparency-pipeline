"""FCC Resolution #2 (entity -> source-local key), ADR-0011.

resolve(entity) -> ResolutionResult with the entity's FRN as source_key.

Priority order:
1. external_id_exact — the entity already carries an FRN external_id (the
   common case once discovery/Layer-2 has attached one). Deterministic, HIGH.
2. name fuzzy — optional fallback against a caller-supplied name->FRN index
   (rapidfuzz WRatio). Cross-source name bridging is really Layer-2/D3 work and
   carries a merge tier (design/entity-discovery.md); this fallback exists so a
   caller that already holds an index can resolve cheaply. Without an index we
   return unresolved rather than scan the 458 MB app_party.dat on every call.

No curated FRN bridge is built here: FCC<->SEC has no deterministic key
(EIN-bridge is a dead end — FCC keys parties by FRN, SEC by CIK/EIN, namespaces
disjoint). Fuzzy/address matching is the only bridge and it belongs in Layer 2.
"""
from __future__ import annotations

from typing import Dict, Optional

from pipeline.contracts import (
    Confidence,
    Entity,
    IdType,
    ResolutionResult,
)
from pipeline.extractors.fcc.extract import normalize_frn

# rapidfuzz is a project dependency; imported lazily so the exact path never needs it.
_FUZZY_HIGH = 92
_FUZZY_MED = 82


def resolve(
    entity: Entity,
    name_index: Optional[Dict[str, str]] = None,
) -> ResolutionResult:
    """Resolve an entity to its FCC FRN.

    Args:
        entity: the entity to resolve.
        name_index: optional {UPPER_name: frn} map for the fuzzy fallback.
    """
    # 1. Exact external-id path -------------------------------------------------
    for ext in entity.external_ids:
        if ext.id_type is IdType.FRN:
            frn = normalize_frn(ext.id_value)
            if frn:
                return ResolutionResult(
                    source_key=frn,
                    confidence=Confidence.HIGH,
                    method="external_id_exact",
                )

    # 2. Name fuzzy fallback (only if the caller supplied an index) ------------
    if name_index:
        return _resolve_by_name(entity, name_index)

    return ResolutionResult(
        source_key=None,
        confidence=Confidence.LOW,
        method="unresolved_no_frn",
        candidates=[],
    )


def _resolve_by_name(entity: Entity, name_index: Dict[str, str]) -> ResolutionResult:
    from rapidfuzz import process, fuzz

    query = (entity.canonical_name or "").upper().strip()
    if not query:
        return ResolutionResult(None, Confidence.LOW, "unresolved_no_name")

    matches = process.extract(query, name_index.keys(), scorer=fuzz.WRatio, limit=5)
    if not matches:
        return ResolutionResult(None, Confidence.LOW, "unresolved_no_candidates")

    best_name, best_score, _ = matches[0]
    candidates = [
        {"name": n, "frn": name_index[n], "score": round(s, 1)} for n, s, _ in matches
    ]
    if best_score >= _FUZZY_HIGH:
        conf = Confidence.HIGH
    elif best_score >= _FUZZY_MED:
        conf = Confidence.MEDIUM
    else:
        # Below the medium bar: surface candidates but do not assert a key.
        return ResolutionResult(
            source_key=None,
            confidence=Confidence.LOW,
            method="name_fuzzy_below_floor",
            candidates=candidates,
        )
    return ResolutionResult(
        source_key=name_index[best_name],
        confidence=conf,
        method="name_fuzzy_wratio",
        candidates=candidates[1:],
    )
