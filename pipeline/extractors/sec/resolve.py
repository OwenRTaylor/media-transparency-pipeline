"""SEC EDGAR Resolution #2 — entity -> its SEC source key (CIK).

Per ADR-0011 two-layer resolution: this is source-local. Given an Entity, return
a ResolutionResult carrying the CIK (source_key), how it was found (method),
confidence, and rejected candidates.

Two paths:
  1. Deterministic — the entity already carries a CIK external id => exact, HIGH.
     This is the honest "official" path: no probabilistic judgment by our code.
  2. Fuzzy — no CIK on hand => match canonical_name against a candidate index
     (list of {"cik","name"}) with rapidfuzz WRatio. This is a *Likely* inference;
     it is graded high/med/low and, when consumed by a cross-source merge, the
     caller MUST record that tier on the resulting external_id (never merge
     silently — design/entity-discovery.md rule 3).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz, process, utils

from pipeline.contracts import (
    Confidence,
    Entity,
    IdType,
    ResolutionResult,
)

# WRatio score -> confidence tier. Provisional cutoffs — to be calibrated against
# real data (the D3 floor exercise). Kept here so calibration has one home.
_HIGH_CUTOFF = 92.0
_MEDIUM_CUTOFF = 80.0


def _tier(score: float) -> Confidence:
    if score >= _HIGH_CUTOFF:
        return Confidence.HIGH
    if score >= _MEDIUM_CUTOFF:
        return Confidence.MEDIUM
    return Confidence.LOW


def _cik_from_entity(entity: Entity) -> Optional[str]:
    for ext in entity.external_ids:
        if ext.id_type is IdType.CIK:
            return ext.id_value
    return None


def resolve(
    entity: Entity,
    candidates: Optional[List[Dict[str, Any]]] = None,
) -> ResolutionResult:
    """Resolve an entity to its CIK.

    candidates: optional list of {"cik": str, "name": str} to fuzzy-match against
    when the entity carries no CIK (e.g. the SEC media-candidate discovery list).
    """
    # Path 1 — deterministic.
    cik = _cik_from_entity(entity)
    if cik:
        return ResolutionResult(
            source_key=cik,
            confidence=Confidence.HIGH,
            method="external_id_cik_exact",
        )

    # Path 2 — fuzzy name match.
    if not candidates:
        return ResolutionResult(
            source_key=None,
            confidence=Confidence.LOW,
            method="no_cik_no_candidates",
        )

    names = [c["name"] for c in candidates]
    hits = process.extract(
        entity.canonical_name,
        names,
        scorer=fuzz.WRatio,
        processor=utils.default_process,  # lowercase, strip punctuation
        limit=5,
    )
    if not hits:
        return ResolutionResult(
            source_key=None, confidence=Confidence.LOW, method="rapidfuzz_wratio_nohit"
        )

    best_name, best_score, best_idx = hits[0]
    alternates = [
        {"cik": candidates[idx]["cik"], "name": name, "score": round(score, 1)}
        for name, score, idx in hits[1:]
    ]
    return ResolutionResult(
        source_key=candidates[best_idx]["cik"],
        confidence=_tier(best_score),
        method="rapidfuzz_wratio",
        candidates=alternates,
    )
