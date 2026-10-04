"""SEC EDGAR Layer-1 extractor — entity + identifiers from local bulk `submissions/`.

Scope (v1 slice): read one company's local `submissions/CIK##########.json`
(bulk data, INV-14 — no live fetch) and emit an ExtractorResult:
  - one Entity (canonical name, aliases, attributes, external ids: CIK/EIN/LEI)
  - provenance for every external id and sourced attribute
  - GAP records (ADR-0016) for ownership documents that exist in the filing
    index (SC 13D, DEF 14A, 10-K Ex-21) but have no parser yet
  - a CoverageLog

What this extractor does NOT do yet: parse ownership relationships. Those live
in SC 13D / DEF 14A / Exhibit 21 documents; until those parsers exist the edges
are surfaced honestly as gaps, not silently dropped (INV-19, INV-20).

Real-data note (2026-09-19): `submissions` is aggregated company *metadata*,
not one filing, so its SourceDocument carries filing_date=None. Attribute-level
dates would come from the specific confirming filing once those are parsed.

SDK-confinement (INV-30): reading local bulk JSON needs no SEC SDK. edgartools,
if ever used, stays inside this extractors/sec/ package as a fetch backend only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pipeline.contracts import (
    AccessLink,
    AccessTier,
    Confidence,
    CoverageLog,
    Entity,
    EntityType,
    ExternalId,
    ExtractionMethod,
    ExtractorResult,
    IdType,
    ProvenanceRecord,
    RecordType,
    SourceDocument,
    TargetType,
)

SOURCE = "sec_edgar"
ANCHOR_TYPE = "sec_submissions"
ANCHOR_SCHEMA_VERSION = 1
CODE_SHA = "42b31d2"  # bump per release; reproducibility (INV: extraction_code_sha)

# Default location of the local bulk submissions dump.
SUBMISSIONS_DIR = os.path.join("unfiltered_data", "submissions")

# Forms in the filing index that carry ownership facts we can't extract yet.
# form prefix -> the kind of edge it would yield (for gap records).
OWNERSHIP_FORMS = {
    "SC 13D": "beneficial_ownership_over_5pct",
    "SC 13G": "beneficial_ownership_over_5pct",
    "DEF 14A": "board_and_major_holders",
    "10-K": "subsidiaries_exhibit_21",
}

# submissions metadata fields promoted to entity attributes (only if non-empty).
_ATTR_FIELDS = (
    "sic",
    "sicDescription",
    "entityType",
    "stateOfIncorporation",
    "fiscalYearEnd",
    "category",
)


def _cik_padded(cik: str) -> str:
    """Zero-pad to the 10-digit form used in bulk filenames."""
    return str(cik).lstrip("0").zfill(10)


def _submissions_path(cik: str, submissions_dir: str) -> str:
    return os.path.join(submissions_dir, f"CIK{_cik_padded(cik)}.json")


def _local_id(cik: str) -> str:
    """Provisional in-result id. Layer-3 assigns the real stable entity id (INV-1);
    these ids only wire provenance -> targets *within* this ExtractorResult."""
    return f"sec-cik-{_cik_padded(cik)}"


def _source_document(cik: str, path: str) -> SourceDocument:
    padded = _cik_padded(cik)
    return SourceDocument(
        source=SOURCE,
        doc_type="submissions_metadata",
        filing_date=None,  # aggregated metadata — no single filing date (see module note)
        document_id=f"submissions/CIK{padded}.json",
        access_links=[
            # Tier A — canonical public URL (recorded, not fetched — INV-14/no-WebFetch)
            AccessLink(AccessTier.A, f"https://data.sec.gov/submissions/CIK{padded}.json"),
            # Tier B — bulk dump member
            AccessLink(AccessTier.B, "sec_bulk_submissions", row_id=f"CIK{padded}.json"),
            # Tier C — local cache (the file on disk)
            AccessLink(AccessTier.C, path),
        ],
    )


def _prov(
    target_type: TargetType,
    target_id: str,
    src_doc: SourceDocument,
    anchor_payload: Dict[str, Any],
    *,
    raw: Optional[Dict[str, Any]] = None,
) -> ProvenanceRecord:
    """An EXTRACTION record from an official source, deterministic => HIGH."""
    return ProvenanceRecord(
        record_type=RecordType.EXTRACTION,
        target_type=target_type,
        target_id=target_id,
        source_document=src_doc,
        anchor_type=ANCHOR_TYPE,
        anchor_payload=anchor_payload,
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        extraction_code_sha=CODE_SHA,
        created_at=datetime.now(),
        extraction_method=ExtractionMethod.AUTOMATED,
        confidence=Confidence.HIGH,
        raw_source_row=raw,
    )


def _gap(
    target_id: str,
    src_doc: SourceDocument,
    data_point: str,
    gap_reason: str,
    accessions: List[str],
) -> ProvenanceRecord:
    """A GAP record (ADR-0016): the data exists in the source but no parser yet."""
    return ProvenanceRecord(
        record_type=RecordType.GAP,
        target_type=TargetType.ENTITY,
        target_id=target_id,
        source_document=src_doc,
        anchor_type=ANCHOR_TYPE,
        anchor_payload={
            "data_point": data_point,
            "gap_reason": gap_reason,
            "accession_numbers": accessions,
        },
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        extraction_code_sha=CODE_SHA,
        created_at=datetime.now(),
        # extraction_method + confidence stay None for gaps (contract-enforced).
    )


def _external_ids(rec: Dict[str, Any]) -> List[ExternalId]:
    """CIK is always native. EIN/LEI included when present. All native (no merge)."""
    ids = [ExternalId(IdType.CIK, _cik_padded(rec["cik"]))]
    if rec.get("ein"):
        ids.append(ExternalId(IdType.EIN, str(rec["ein"])))
    if rec.get("lei"):
        ids.append(ExternalId(IdType.LEI, str(rec["lei"])))
    return ids


def _attributes(rec: Dict[str, Any]) -> Dict[str, Any]:
    attrs = {k: rec[k] for k in _ATTR_FIELDS if rec.get(k)}
    biz = (rec.get("addresses") or {}).get("business") or {}
    if biz.get("street1"):
        attrs["business_address"] = {
            k: biz.get(k) for k in ("street1", "street2", "city", "stateOrCountry", "zipCode")
            if biz.get(k)
        }
    if rec.get("website"):
        attrs["website"] = rec["website"]
    return attrs


def _ownership_gaps(
    rec: Dict[str, Any], local_id: str, src_doc: SourceDocument
) -> List[ProvenanceRecord]:
    """Group ownership-relevant filings by form and emit one gap record per kind."""
    recent = (rec.get("filings") or {}).get("recent") or {}
    forms = recent.get("form", [])
    accns = recent.get("accessionNumber", [])
    gaps: List[ProvenanceRecord] = []
    for prefix, data_point in OWNERSHIP_FORMS.items():
        hits = [accns[i] for i, f in enumerate(forms) if str(f).startswith(prefix)]
        if hits:
            gaps.append(
                _gap(
                    local_id,
                    src_doc,
                    data_point=data_point,
                    gap_reason=f"{prefix} present in filing index; parser not implemented",
                    accessions=hits,
                )
            )
    return gaps


def extract(cik: str, submissions_dir: str = SUBMISSIONS_DIR) -> ExtractorResult:
    """Extract one company's entity + identifiers from local bulk submissions.

    Returns an empty-but-honest ExtractorResult (coverage_log records the miss)
    when the CIK is not present in the local dump — trail-end honest (INV-19).
    """
    path = _submissions_path(cik, submissions_dir)
    padded = _cik_padded(cik)

    if not os.path.exists(path):
        return ExtractorResult(
            coverage_log=CoverageLog(
                source=SOURCE,
                queried=[padded],
                not_found=[padded],
                notes=[f"CIK{padded} absent from local bulk submissions dump"],
            )
        )

    with open(path) as fh:
        rec = json.load(fh)

    local_id = _local_id(cik)
    src_doc = _source_document(cik, path)

    entity = Entity(
        id="",  # Layer-3 assigns the stable id (INV-1); provenance uses local_id below
        type=EntityType.COMPANY,
        canonical_name=rec.get("name", "").strip(),
        aliases=[fn.get("name") for fn in rec.get("formerNames", []) if fn.get("name")],
        attributes=_attributes(rec),
        external_ids=_external_ids(rec),
        domains=[rec["website"]] if rec.get("website") else [],
        raw_source_row=rec,
    )

    provenance: List[ProvenanceRecord] = []

    # One provenance record per external id.
    for ext in entity.external_ids:
        provenance.append(
            _prov(
                TargetType.EXTERNAL_ID,
                f"{local_id}:extid:{ext.id_type.value}:{ext.id_value}",
                src_doc,
                {"cik": padded, "field": ext.id_type.value},
            )
        )

    # One provenance record per sourced attribute.
    for attr_name in entity.attributes:
        provenance.append(
            _prov(
                TargetType.ENTITY_ATTRIBUTE,
                f"{local_id}:attr:{attr_name}",
                src_doc,
                {"cik": padded, "field": attr_name},
            )
        )

    # Ownership edges we can see but can't parse yet -> gaps.
    provenance.extend(_ownership_gaps(rec, local_id, src_doc))

    n_forms = len(((rec.get("filings") or {}).get("recent") or {}).get("form", []))
    coverage = CoverageLog(
        source=SOURCE,
        queried=[padded],
        found=[padded],
        notes=[
            f"{n_forms} filings in local index",
            f"{sum(1 for p in provenance if p.record_type is RecordType.GAP)} ownership gap(s) flagged",
            "no ownership relationships extracted — SC13D/DEF14A/Ex-21 parsers pending",
        ],
    )

    return ExtractorResult(
        entities=[entity],
        relationships=[],  # none derivable from submissions metadata alone
        provenance=provenance,
        coverage_log=coverage,
    )


def _summarize(result: ExtractorResult) -> None:
    for e in result.entities:
        print(f"ENTITY  {e.canonical_name}  [{e.type.value}]")
        print(f"  aliases: {e.aliases or '—'}")
        print(f"  external_ids: {[(x.id_type.value, x.id_value) for x in e.external_ids]}")
        print(f"  attributes: {list(e.attributes.keys())}")
        print(f"  domains: {e.domains or '—'}")
    ext = sum(1 for p in result.provenance if p.record_type is RecordType.EXTRACTION)
    gap = sum(1 for p in result.provenance if p.record_type is RecordType.GAP)
    print(f"PROVENANCE  {ext} extraction, {gap} gap")
    for p in result.provenance:
        if p.record_type is RecordType.GAP:
            print(f"  GAP  {p.anchor_payload['data_point']}  ({len(p.anchor_payload['accession_numbers'])} filing(s))")
    if result.coverage_log:
        print("COVERAGE ", "; ".join(result.coverage_log.notes))


if __name__ == "__main__":
    import sys

    cik_arg = sys.argv[1] if len(sys.argv) > 1 else "788511"  # Fox Television Stations Inc
    _summarize(extract(cik_arg))
