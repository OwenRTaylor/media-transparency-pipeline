"""Layer 3 — load extractor output into DuckDB staging tables (common schema).

Consumes `list[ExtractorResult]` (pipeline/contracts.py) — the in-memory
objects every Layer-1 extractor emits — and flattens them into the flat
`stg_*` tables (schema.py). Embedded SourceDocument + AccessLink objects
(contracts.py: provenance embeds them) are lifted out here and keyed by a
fingerprint so export can dedupe identical documents.

Nothing is resolved or deduped at this stage; staging is a faithful,
queryable mirror of what the extractors emitted. Cross-source resolution
lives in dedupe.py; id assignment + document dedupe live in export.py.
"""
from __future__ import annotations

import json
from typing import Any, List

import duckdb

from pipeline.contracts import ExtractorResult
from pipeline.staging import schema
from pipeline.staging.keys import doc_fingerprint, rel_natural_key


def _json(value: Any) -> str | None:
    """Serialize a dict/list field to a JSON string (dates -> isoformat via str)."""
    if value is None:
        return None
    return json.dumps(value, default=str, sort_keys=True)


def create_staging(con: duckdb.DuckDBPyConnection) -> None:
    """(Re)create the empty staging tables. Staging is disposable per run."""
    for table in schema.STAGING_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(schema.STAGING_DDL)


def stage(results: List[ExtractorResult],
          con: duckdb.DuckDBPyConnection | None = None) -> duckdb.DuckDBPyConnection:
    """Load extractor results into a fresh in-memory DuckDB (or given con).

    Returns the connection so validate.py / export.py can read from it.
    """
    con = con or duckdb.connect(":memory:")
    create_staging(con)

    prov_idx = 0
    for result in results:
        _stage_entities(con, result)
        _stage_relationships(con, result)
        prov_idx = _stage_provenance(con, result, prov_idx)

    return con


def _stage_entities(con: duckdb.DuckDBPyConnection, result: ExtractorResult) -> None:
    for e in result.entities:
        con.execute(
            "INSERT INTO stg_entities VALUES (?, ?, ?, ?, ?, ?, ?)",
            [e.id, e.type.value, e.canonical_name, _json(e.aliases),
             _json(e.attributes), _json(e.domains), _json(e.raw_source_row)],
        )
        for xid in e.external_ids:
            con.execute(
                "INSERT INTO stg_external_ids VALUES (?, ?, ?, ?, ?)",
                [e.id, xid.id_type.value, xid.id_value,
                 xid.merge_confidence.value if xid.merge_confidence else None,
                 xid.merge_method],
            )
        for domain in e.domains:
            con.execute(
                "INSERT INTO stg_domains VALUES (?, ?, ?)",
                [domain, e.id, False],
            )


def _stage_relationships(con: duckdb.DuckDBPyConnection, result: ExtractorResult) -> None:
    for r in result.relationships:
        con.execute(
            "INSERT INTO stg_relationships VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [rel_natural_key(r), r.source_entity_id, r.target_entity_id,
             r.type.value, r.confidence.value, r.last_verified, r.status.value,
             r.qualifier, r.detail_type, _json(r.detail_payload),
             r.detail_schema_version],
        )


def _stage_provenance(con: duckdb.DuckDBPyConnection, result: ExtractorResult,
                      prov_idx: int) -> int:
    for p in result.provenance:
        doc = p.source_document
        fp = doc_fingerprint(doc)

        # Stage the embedded document + its links (deduped on write in export).
        con.execute(
            "INSERT INTO stg_source_documents VALUES (?, ?, ?, ?, ?)",
            [fp, doc.source, doc.doc_type, doc.filing_date, doc.document_id],
        )
        for al in doc.access_links:
            con.execute(
                "INSERT INTO stg_access_links VALUES (?, ?, ?, ?)",
                [fp, al.tier.value, al.location, al.row_id],
            )

        con.execute(
            "INSERT INTO stg_provenance VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [prov_idx, p.record_type.value, p.target_type.value, p.target_id, fp,
             p.anchor_type, _json(p.anchor_payload), p.anchor_schema_version,
             p.extraction_method.value if p.extraction_method else None,
             p.extraction_code_sha,
             p.confidence.value if p.confidence else None,
             _json(p.raw_source_row), p.created_at],
        )
        prov_idx += 1
    return prov_idx
