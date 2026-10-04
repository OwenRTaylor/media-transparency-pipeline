"""FCC LMS Layer-1 extractor (vertical slice: FRN -> licensee company).

Given an FRN, emits an ``ExtractorResult``:
- one ``Entity(type=COMPANY)`` for the licensee behind that FRN, carrying the
  FRN and each of its station ``facility_id``s as ``external_ids``;
- one ``ProvenanceRecord`` per external_id (``target_type=EXTERNAL_ID``,
  ``anchor_type="fcc_lms_row"``, ``extraction_method=AUTOMATED``); and
- a ``CoverageLog`` of what was queried / found / not found.

v1 emits only ``(source_official=true, extraction_method=automated)`` — the
official-ness lives on the `sources` table (Layer 3 knows ``fcc_lms`` is
official); this module marks the extraction axis as AUTOMATED (INV-10).

Real-data quirks handled (see fcc-lms-data-profile.md):
- FRN sentinel-nulls ("", "NO FRN", "N/A", "NONE") normalized away (#8).
- FRN<->entity is M:N and names change under a stable FRN (#10, #11): the FRN's
  many legal_party_name spellings are collapsed by frequency into one canonical
  name + aliases, not treated as an error.
- Junk in the name column: literal "INDIVIDUAL" placeholder and addresses
  pasted into legal_party_name are detected and excluded from canonical-name
  selection (still kept in the raw row).

Data path (INV-14, bulk over API):
  app_party.dat          FRN -> legal_party_name + application_id (identity)
  application_facility.dat  application_id -> facility_id + licensee_name (stations)
"""
from __future__ import annotations

import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

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
from pipeline.extractors.fcc.dat_reader import iter_records
from pipeline.extractors.fcc.name_core import distinctive_tokens

SOURCE = "fcc_lms"
DEFAULT_DUMP_DIR = Path("unfiltered_data/Current_LMS_Dump")
ANCHOR_TYPE = "fcc_lms_row"
ANCHOR_SCHEMA_VERSION = 1

# FCC bulk-download landing page (Tier B location for every LMS row).
LMS_BULK_URL = "https://enterpriseefiling.fcc.gov/dataentry/public/tv/lmsDatabase.html"

# Sentinel-null variants seen in the FRN column (profile fragility #8).
FRN_NULLS = {"", "NO FRN", "N/A", "NA", "NONE", "N\\A"}
# Placeholder the FCC writes when the filing party is a natural person (#not-a-company).
NAME_PLACEHOLDERS = {"INDIVIDUAL", "SEE EXHIBIT", "SEE EXHIBIT 1", "SEE ATTACHED"}
# "starts with a street number" / PO box — address pasted into the name field.
_ADDRESS_IN_NAME = re.compile(r"^\s*(\d+\s+\w|P\.?\s*O\.?\s*BOX|POST OFFICE)", re.IGNORECASE)


def normalize_frn(value: Optional[str]) -> Optional[str]:
    """Trim and null-out sentinel FRN values. Returns None if not a real FRN."""
    v = (value or "").strip().upper()
    return None if v in FRN_NULLS else v


def is_junk_name(name: str) -> bool:
    """True if a legal_party_name is a placeholder or a pasted-in address."""
    n = (name or "").strip()
    if not n:
        return True
    if n.upper() in NAME_PLACEHOLDERS:
        return True
    return bool(_ADDRESS_IN_NAME.match(n))


def _git_sha() -> str:
    """Git SHA of the producing code (reproducibility, INV-3). 'uncommitted' if unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[3],
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _source_document(dump_file: Path) -> SourceDocument:
    """One SourceDocument per bulk table. filing_date=None: a bulk dump is not a
    dated filing (per-row filing dates would come from the application table)."""
    return SourceDocument(
        source=SOURCE,
        doc_type="fcc_lms_bulk",
        filing_date=None,
        document_id=dump_file.name,
        access_links=[
            AccessLink(tier=AccessTier.B, location=LMS_BULK_URL, row_id=None),
            AccessLink(tier=AccessTier.C, location=str(dump_file)),
        ],
    )


def _provenance_for_external_id(
    id_value: str,
    table: str,
    dump_file: Path,
    primary_key: str,
    raw_row: Dict[str, str],
    code_sha: str,
    created_at: datetime,
    extra_anchor: Optional[Dict] = None,
) -> ProvenanceRecord:
    doc = _source_document(dump_file)
    # Tier-B row_id: this row's within-file primary key (or a hash if PK absent).
    doc.access_links[0].row_id = f"{table}:{primary_key}"
    anchor_payload = {
        "dump_file": dump_file.name,
        "table": table,
        "primary_key": primary_key,
    }
    if extra_anchor:
        anchor_payload.update(extra_anchor)
    return ProvenanceRecord(
        record_type=RecordType.EXTRACTION,
        target_type=TargetType.EXTERNAL_ID,
        target_id=id_value,  # Layer-3 relinks to the assigned external_id row id
        source_document=doc,
        anchor_type=ANCHOR_TYPE,
        anchor_payload=anchor_payload,
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        extraction_code_sha=code_sha,
        created_at=created_at,
        extraction_method=ExtractionMethod.AUTOMATED,
        confidence=Confidence.HIGH,  # deterministic exact FRN row; official-ness is on `sources`
        raw_source_row=raw_row,
    )


def _row_pk(row: Dict[str, str], candidates: List[str]) -> str:
    """Best available within-file primary key; falls back to a row hash."""
    for col in candidates:
        v = (row.get(col) or "").strip()
        if v:
            return v
    return f"rowhash:{hash(tuple(sorted(row.items()))) & 0xFFFFFFFF:08x}"


def extract(frn: str, dump_dir: str | Path = DEFAULT_DUMP_DIR) -> ExtractorResult:
    """Extract the licensee company for one FRN. See module docstring."""
    target = normalize_frn(frn)
    if target is None:
        raise ValueError(f"{frn!r} is not a real FRN (sentinel-null or empty)")

    dump_dir = Path(dump_dir)
    party_path = dump_dir / "app_party.dat"
    facility_path = dump_dir / "application_facility.dat"
    code_sha = _git_sha()
    created_at = datetime.now(timezone.utc)

    # --- Pass 1: app_party.dat -> identity (name history) + application ids ----
    name_counts: Counter[str] = Counter()
    junk_names: Set[str] = set()
    application_ids: Set[str] = set()
    party_rep_row: Optional[Dict[str, str]] = None
    party_rep_pk: Optional[str] = None
    party_row_count = 0

    for row in iter_records(party_path):
        if normalize_frn(row.get("apar_frn")) != target:
            continue
        party_row_count += 1
        app_id = (row.get("apar_aapp_application_id") or "").strip()
        if app_id:
            application_ids.add(app_id)
        name = (row.get("apar_legal_party_name") or "").strip()
        if is_junk_name(name):
            if name:
                junk_names.add(name)
            continue
        name_counts[name] += 1
        # Keep the row backing the current modal name as the FRN's evidence row.
        if party_rep_row is None or name_counts[name] == name_counts.most_common(1)[0][1]:
            party_rep_row = row
            party_rep_pk = _row_pk(row, ["apar_party_record_id", "apar_party_id"])

    if party_row_count == 0:
        # Trail-end honest (INV-19): queried, not found. Empty result + coverage.
        return ExtractorResult(
            coverage_log=CoverageLog(
                source=SOURCE,
                queried=[target],
                not_found=[target],
                notes=[f"FRN {target} absent from app_party.dat"],
            )
        )

    canonical, aliases, counterparties = _partition_names(name_counts)

    # --- Pass 2: application_facility.dat -> stations (facility ids) -----------
    # dict facility_id -> representative row (first seen active), for dedupe (#9).
    facilities: Dict[str, Dict[str, str]] = {}
    for row in iter_records(facility_path):
        if (row.get("afac_application_id") or "").strip() not in application_ids:
            continue
        if (row.get("active_ind") or "").strip().upper() != "Y":
            continue
        fac_id = (row.get("afac_facility_id") or "").strip()
        if fac_id and fac_id not in facilities:
            facilities[fac_id] = row

    # --- Build entity + external ids ------------------------------------------
    external_ids: List[ExternalId] = [ExternalId(id_type=IdType.FRN, id_value=target)]
    for fac_id in sorted(facilities, key=lambda x: int(x) if x.isdigit() else 0):
        external_ids.append(ExternalId(id_type=IdType.FACILITY_ID, id_value=fac_id))

    entity = Entity(
        id="",  # Layer-3 assigns the stable id (INV-1); matched via external_ids
        type=EntityType.COMPANY,
        canonical_name=canonical,
        aliases=aliases,
        external_ids=external_ids,
        attributes={
            "name_history": dict(name_counts),  # frequency of each spelling under this FRN
            "station_count": len(facilities),
            # Names co-occurring under this FRN that share NO distinctive token with
            # the canonical name — counterparties on transfer/assignment filings
            # (e.g. the seller in an acquisition), NOT renamings of this entity.
            # Quarantined here, never in `aliases`, so the SEC<->FCC fuzzy merge
            # (which consumes canonical_name + aliases) cannot false-merge Fox=Nexstar.
            # Layer 2 resolves these to their own entities via their own FRNs.
            "possible_counterparties": counterparties,
        },
        raw_source_row=party_rep_row,
    )

    # --- Provenance: one record per external id -------------------------------
    provenance: List[ProvenanceRecord] = [
        _provenance_for_external_id(
            id_value=target,
            table="app_party",
            dump_file=party_path,
            primary_key=party_rep_pk or "unknown",
            raw_row=party_rep_row or {},
            code_sha=code_sha,
            created_at=created_at,
        )
    ]
    for fac_id, row in facilities.items():
        provenance.append(
            _provenance_for_external_id(
                id_value=fac_id,
                table="application_facility",
                dump_file=facility_path,
                primary_key=_row_pk(row, ["afac_facility_record_id", "afac_facility_id"]),
                raw_row=row,
                code_sha=code_sha,
                created_at=created_at,
                extra_anchor={"application_id": (row.get("afac_application_id") or "").strip()},
            )
        )

    notes = [
        f"{party_row_count} party rows under FRN {target}",
        f"{len(name_counts)} distinct company-name spellings; {len(aliases)} kept as aliases "
        f"(share canonical's distinctive tokens, profile #11 rename)",
        f"{len(facilities)} active facilities across {len(application_ids)} applications",
    ]
    if counterparties:
        notes.append(
            f"quarantined {len(counterparties)} counterparty name(s) from aliases "
            f"(no distinctive-token overlap with canonical — transfer co-parties, not renames): "
            f"{[c['name'] for c in counterparties][:5]}"
        )
    if junk_names:
        notes.append(f"excluded {len(junk_names)} junk name(s) from canonical: {sorted(junk_names)[:5]}")

    coverage = CoverageLog(
        source=SOURCE,
        queried=[target],
        found=[target],
        notes=notes,
    )
    return ExtractorResult(
        entities=[entity],
        relationships=[],  # licensee->station edges are Layer-2 traversal, out of this slice
        provenance=provenance,
        coverage_log=coverage,
    )


def _partition_names(
    name_counts: Counter[str],
) -> tuple[str, List[str], List[Dict[str, object]]]:
    """Split the names seen under one FRN into canonical / aliases / counterparties.

    - canonical = modal legal_party_name.
    - alias     = a distinct spelling that shares >=1 distinctive token with the
                  canonical name (genuine rename / corporate-form variant, e.g.
                  "FOX ... INC." vs "FOX ... LLC"). Deduped case-insensitively;
                  the canonical spelling itself is excluded.
    - counterparty = a name that shares NO distinctive token with the canonical
                  (a transfer/assignment co-party recorded under this FRN, e.g.
                  "NEXSTAR BROADCASTING, INC." under Fox's FRN). Returned as
                  labeled data {name, rows}, never folded into aliases.
    """
    if not name_counts:
        return "UNKNOWN (no non-junk name under FRN)", [], []
    ranked = [n for n, _ in name_counts.most_common()]
    canonical = ranked[0]
    canon_dist = distinctive_tokens(canonical)

    aliases: List[str] = []
    counterparties: List[Dict[str, object]] = []
    seen_folded = {canonical.casefold()}
    for name in ranked[1:]:
        shares_core = bool(canon_dist and (distinctive_tokens(name) & canon_dist))
        if shares_core:
            if name.casefold() not in seen_folded:  # drop pure case variants of a kept name
                aliases.append(name)
                seen_folded.add(name.casefold())
        else:
            counterparties.append({"name": name, "rows": name_counts[name]})
    return canonical, aliases, counterparties


def _print_result(result: ExtractorResult) -> None:
    """Human-inspectable dump of an ExtractorResult (smoke-test / --done check)."""
    print("=" * 70)
    for e in result.entities:
        print(f"ENTITY  type={e.type.value}  canonical_name={e.canonical_name!r}")
        frns = [x.id_value for x in e.external_ids if x.id_type is IdType.FRN]
        facs = [x.id_value for x in e.external_ids if x.id_type is IdType.FACILITY_ID]
        print(f"  external_ids: {len(e.external_ids)}  (FRN={frns}, facility_ids={len(facs)})")
        print(f"  aliases ({len(e.aliases)}): {e.aliases}")
        print(f"  possible_counterparties (quarantined): {e.attributes.get('possible_counterparties')}")
        print(f"  facility_id sample: {facs[:10]}")
        print(f"  attributes.station_count: {e.attributes.get('station_count')}")
    print(f"\nPROVENANCE records: {len(result.provenance)}")
    for p in result.provenance[:3]:
        print(f"  [{p.target_type.value}] target_id={p.target_id}  "
              f"anchor={p.anchor_type} {p.anchor_payload}  "
              f"method={p.extraction_method.value}  conf={p.confidence.value}")
    if len(result.provenance) > 3:
        print(f"  ... +{len(result.provenance) - 3} more (one per external_id)")
    print(f"\nCOVERAGE  source={result.coverage_log.source}  "
          f"queried={result.coverage_log.queried}  found={result.coverage_log.found}  "
          f"not_found={result.coverage_log.not_found}")
    for n in result.coverage_log.notes:
        print(f"  - {n}")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    frn_arg = sys.argv[1] if len(sys.argv) > 1 else "0005795067"  # Fox Television Stations
    dump = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DUMP_DIR
    _print_result(extract(frn_arg, dump))
