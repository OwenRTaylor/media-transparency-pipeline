"""Cross-source identity resolution — the SEC<->FCC merge hop.

SEC (CIK/EIN) and FCC (FRN) are disjoint namespaces with no deterministic bridge
(handoff 2026-09-18), so an identity assertion "this FCC licensee IS this SEC
filer" is a *probabilistic inference*, not an extraction. This module makes that
assertion explicitly, with its own tier, and records it as provenance.

Load-bearing rule (design/entity-discovery.md rule 3 — "never merge silently"):
merging attaches the other source's external_ids to one entity; every attached id
carries merge_confidence + merge_method, AND a provenance record documents the
merge. merge_entities() *raises* if asked to merge without a decided tier. This is
what keeps the trust-chain honest: the identity hop is never an invisible weak link.

Matching policy (provisional — the D3 floor is not yet empirically calibrated):
  * distinctive-token overlap is REQUIRED (the false-positive killer; WRatio alone
    scored unrelated GANNETT at 85 vs Fox). Shared identity words, not domain filler.
  * WRatio tier on top of the guard:  >=92 HIGH,  >=82 MEDIUM,  else no merge.
  * Address is a positive-only tiebreaker, NEVER a requirement or veto. Real-data
    reason (Fox, 2026-09-19): the FCC party address is the licensee's DC regulatory
    *counsel* (444 N Capitol St), not its HQ (10201 W Pico Blvd, LA). Address
    disagreement is normal for broadcasters and must not block a good name match;
    and a shared counsel address must not merge unrelated licensees.

Two-axis tier note (ADR-worthy): a merge is the first (source_official=FALSE)
datum the pipeline emits — it is our inference, not a publisher-of-record fact.
That is correct, not a v1-scope violation: INV-10 bars unofficial *sources*
(aggregators/news), while the two-axis model explicitly reserves the "Likely"
tier for our own graded inferences. The server's default (Official-only) view
hides it until the user opens the tier facet.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pipeline.contracts import (
    Confidence,
    Entity,
    ExternalId,
    ExtractionMethod,
    ProvenanceRecord,
    RecordType,
    SourceDocument,
    TargetType,
)
from pipeline.resolution.names import distinctive_tokens, name_score

# Provisional tier cutoffs on WRatio. To be replaced by the empirical D3 floor.
HIGH_CUTOFF = 92.0
MEDIUM_CUTOFF = 82.0

# The merge is a pipeline derivation, not a source filing.
MERGE_SOURCE = "pipeline_resolution"  # source_official = FALSE (see module note)
MERGE_ANCHOR_TYPE = "cross_source_merge"
MERGE_ANCHOR_SCHEMA_VERSION = 1


def _code_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@dataclass
class MergeDecision:
    """Whether two entities are the same, and how strongly we believe it."""
    matched: bool
    score: float
    shared_tokens: List[str]
    tier: Optional[Confidence] = None      # None <=> not matched
    address_agreement: Optional[bool] = None  # None = not evaluable (no address on a side)
    method: str = ""
    reason: str = ""


def _tier(score: float) -> Optional[Confidence]:
    if score >= HIGH_CUTOFF:
        return Confidence.HIGH
    if score >= MEDIUM_CUTOFF:
        return Confidence.MEDIUM
    return None


def _address(entity: Entity) -> Optional[str]:
    """Normalized single-line address from entity.attributes, if present."""
    addr = entity.attributes.get("business_address")
    if not isinstance(addr, dict):
        return None
    parts = [addr.get("street1"), addr.get("city"), addr.get("stateOrCountry")]
    joined = " ".join(str(p).upper().strip() for p in parts if p)
    return joined or None


def decide(a: Entity, b: Entity) -> MergeDecision:
    """Decide whether entities a and b are the same real-world entity."""
    shared = distinctive_tokens(a.canonical_name) & distinctive_tokens(b.canonical_name)
    score = name_score(a.canonical_name, b.canonical_name)

    # Address corroboration — positive-only (see module note).
    addr_a, addr_b = _address(a), _address(b)
    addr_agree: Optional[bool] = None
    if addr_a and addr_b:
        addr_agree = name_score(addr_a, addr_b) >= 90.0

    if not shared:
        return MergeDecision(
            matched=False, score=score, shared_tokens=[], address_agreement=addr_agree,
            reason="no distinctive-token overlap (false-positive guard)",
        )

    tier = _tier(score)
    if tier is None:
        return MergeDecision(
            matched=False, score=score, shared_tokens=sorted(shared),
            address_agreement=addr_agree,
            reason=f"WRatio {score:.1f} below merge floor {MEDIUM_CUTOFF}",
        )

    # Positive-only tiebreaker: agreeing address can lift MEDIUM->HIGH; disagreement
    # is ignored (broadcasters' FCC address is often DC counsel, not HQ).
    if tier is Confidence.MEDIUM and addr_agree:
        tier = Confidence.HIGH

    method = "name_wratio+distinctive_token_guard"
    if addr_agree:
        method += "+address_corroborated"
    return MergeDecision(
        matched=True, score=score, shared_tokens=sorted(shared), tier=tier,
        address_agreement=addr_agree, method=method,
        reason=f"distinctive tokens {sorted(shared)}, WRatio {score:.1f}",
    )


def merge_entities(
    base: Entity, other: Entity, decision: MergeDecision,
) -> tuple[Entity, List[ProvenanceRecord]]:
    """Fold `other`'s identity into `base`, recording the merge tier on every
    attached external id AND as provenance. Raises if the merge has no tier
    (never merge silently).

    `base` is the entity whose native identity is kept (e.g. the SEC filer); the
    FCC entity's external_ids are attached to it as cross-source ids.
    """
    if not decision.matched or decision.tier is None:
        raise ValueError("refusing to merge without a decided tier (never merge silently)")

    created_at = datetime.now(timezone.utc)
    sha = _code_sha()

    merged = Entity(
        id=base.id,
        type=base.type,
        canonical_name=base.canonical_name,
        aliases=sorted({*base.aliases, *other.aliases, other.canonical_name} - {base.canonical_name}),
        attributes={**other.attributes, **base.attributes},  # base wins on conflict
        external_ids=list(base.external_ids),
        domains=sorted({*base.domains, *other.domains}),
        raw_source_row=base.raw_source_row,
    )

    provenance: List[ProvenanceRecord] = []
    merge_doc = SourceDocument(
        source=MERGE_SOURCE, doc_type="cross_source_merge", filing_date=None,
        document_id=f"merge:{base.canonical_name}~{other.canonical_name}",
        access_links=[],  # a derivation is reachable via anchor + code_sha, not a URL
    )

    # Attach each of `other`'s external ids, stamped with the merge's tier + method.
    for ext in other.external_ids:
        attached = ExternalId(
            id_type=ext.id_type, id_value=ext.id_value,
            merge_confidence=decision.tier, merge_method=decision.method,
        )
        merged.external_ids.append(attached)
        provenance.append(ProvenanceRecord(
            record_type=RecordType.EXTRACTION,
            target_type=TargetType.EXTERNAL_ID,
            target_id=f"{base.id or base.canonical_name}:extid:{ext.id_type.value}:{ext.id_value}",
            source_document=merge_doc,
            anchor_type=MERGE_ANCHOR_TYPE,
            anchor_payload={
                "asserted": f"{other.canonical_name} IS {base.canonical_name}",
                "base_ids": [(x.id_type.value, x.id_value) for x in base.external_ids],
                "attached_id": (ext.id_type.value, ext.id_value),
                "wratio": round(decision.score, 1),
                "shared_tokens": decision.shared_tokens,
                "address_agreement": decision.address_agreement,
            },
            anchor_schema_version=MERGE_ANCHOR_SCHEMA_VERSION,
            extraction_code_sha=sha,
            created_at=created_at,
            extraction_method=ExtractionMethod.AUTOMATED,  # automated inference, not LLM
            confidence=decision.tier,                       # the identity hop's own tier
        ))
    return merged, provenance
