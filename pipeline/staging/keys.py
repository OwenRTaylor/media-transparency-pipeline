"""Natural keys + fingerprints shared by stage.py and export.py.

These are the pre-assignment identifiers. Export turns them into stable DB
ids; validation and provenance-target remapping both rely on them being
computed identically on both sides, so they live in one module.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pipeline.contracts import Relationship, SourceDocument


def rel_natural_key(r: Relationship) -> str:
    """Natural key for a relationship: source|target|type.

    Relationship carries no id field (contracts.py), yet a ProvenanceRecord
    with target_type=relationship must point at one. Convention: extractors
    set such a record's target_id to this same string. Export remaps it to
    the assigned DB relationship id. (Flagged tension — see run_staging report.)
    """
    return f"{r.source_entity_id}|{r.target_entity_id}|{r.type.value}"


def _stable_hash(*parts: Any) -> str:
    """Deterministic short hash — stable across runs (idempotence, INV-12)."""
    blob = json.dumps(parts, default=str, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def doc_fingerprint(doc: SourceDocument) -> str:
    """Identity of a source_document for dedupe.

    A source-native document_id (e.g. SEC accession no.) is authoritative
    within its source. Absent one, fall back to a content hash of the
    document's stable fields + its access-link locations.
    """
    if doc.document_id:
        return _stable_hash("id", doc.source, doc.document_id)
    locations = sorted(
        (al.tier.value, al.location, al.row_id or "") for al in doc.access_links
    )
    return _stable_hash("content", doc.source, doc.doc_type,
                        doc.filing_date, locations)


def rel_db_id(rel_key: str) -> str:
    """Stable opaque DB id for a relationship (from its natural key)."""
    return "rel_" + _stable_hash("rel", rel_key)


def doc_db_id(fingerprint: str) -> str:
    """Stable opaque DB id for a deduped source_document."""
    return "doc_" + _stable_hash("doc", fingerprint)


def entity_db_id(entity_key: str, external_ids: list[tuple[str, str]],
                 canonical_name: str, etype: str) -> str:
    """Assign a stable, opaque DB id for an entity (INV-1: never a name/FRN).

    Preference order for the hash seed, most-stable first:
      1. extractor-provided entity_key (already a resolved stable id)
      2. an external id (cik/ein/frn) — survives name changes
      3. canonical_name+type — last resort (flagged: not name-change-stable)
    The returned id is an opaque "e_<hash>" — the seed is never the literal id.
    """
    if entity_key:
        return "e_" + _stable_hash("key", entity_key)
    for id_type, id_value in external_ids:
        return "e_" + _stable_hash("xid", id_type, id_value)
    return "e_" + _stable_hash("name", canonical_name, etype)
