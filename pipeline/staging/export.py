"""Layer 3 — DuckDB staging -> SQLite export. Idempotent: drop + recreate all tables.

This is where the pipeline stops speaking in natural keys and assigns the stable
DB ids the Node.js server reads (INV-1: opaque ids, never a name/FRN). It also:

  * derives the `sources` table from the source keys seen on documents,
  * dedupes identical `source_documents` (contracts.py embeds a SourceDocument
    per provenance record; the same filing recurs across many facts) and unions
    their access links,
  * remaps every provenance `target_id` from its natural key to the assigned id.

Idempotent (INV-12): all 8 tables are dropped + recreated each run, and all ids
are deterministic hashes of stable keys, so re-running over the same staging
yields byte-identical rows.

Two-axis tier (v1): sources.source_official = 1 for all rows; provenance carries
extraction_method = 'automated' only. Any other combination is excluded upstream.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Dict

import duckdb

from pipeline.staging import schema
from pipeline.staging.keys import doc_db_id, entity_db_id, rel_db_id


def export(con: duckdb.DuckDBPyConnection, sqlite_path: str) -> Dict[str, int]:
    """Write staging -> a fresh SQLite artifact at sqlite_path. Returns row counts."""
    out = sqlite3.connect(sqlite_path)
    out.execute("PRAGMA foreign_keys = ON")
    try:
        _recreate(out)
        entity_ids = _export_entities(con, out)
        _export_external_ids(con, out, entity_ids)
        rel_ids = _export_relationships(con, out, entity_ids)
        _export_sources(con, out)
        doc_ids = _export_source_documents(con, out)
        _export_access_links(con, out, doc_ids)
        _export_provenance(con, out, entity_ids, rel_ids, doc_ids)
        _export_domains(con, out, entity_ids)
        out.commit()
        return _counts(out)
    finally:
        out.close()


def _recreate(out: sqlite3.Connection) -> None:
    for table in reversed(schema.PRODUCTION_TABLES):  # reverse: respect FKs on drop
        out.execute(f"DROP TABLE IF EXISTS {table}")
    out.executescript(schema.PRODUCTION_DDL)


def _external_ids_for(con: duckdb.DuckDBPyConnection, entity_key: str):
    return [(row[0], row[1]) for row in con.execute(
        "SELECT id_type, id_value FROM stg_external_ids WHERE entity_key = ?",
        [entity_key]).fetchall()]


def _export_entities(con: duckdb.DuckDBPyConnection,
                     out: sqlite3.Connection) -> Dict[str, str]:
    """Assign stable entity ids; return {entity_key -> db_id}."""
    id_map: Dict[str, str] = {}
    for key, etype, name, aliases, attributes in con.execute(
        "SELECT entity_key, type, canonical_name, aliases, attributes "
        "FROM stg_entities"
    ).fetchall():
        db_id = entity_db_id(key, _external_ids_for(con, key), name, etype)
        id_map[key] = db_id
        out.execute(
            "INSERT INTO entities (id, type, canonical_name, aliases, attributes) "
            "VALUES (?, ?, ?, ?, ?)",
            [db_id, etype, name, aliases, attributes],
        )
    return id_map


def _export_external_ids(con: duckdb.DuckDBPyConnection, out: sqlite3.Connection,
                         entity_ids: Dict[str, str]) -> None:
    pk = 0
    seen = set()
    for key, id_type, id_value, mconf, mmethod in con.execute(
        "SELECT entity_key, id_type, id_value, merge_confidence, merge_method "
        "FROM stg_external_ids"
    ).fetchall():
        entity_id = entity_ids[key]
        dedupe_key = (entity_id, id_type, id_value)
        if dedupe_key in seen:  # UNIQUE(entity_id,id_type,id_value)
            continue
        seen.add(dedupe_key)
        pk += 1
        out.execute(
            "INSERT INTO entity_external_ids "
            "(id, entity_id, id_type, id_value, merge_confidence, merge_method) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [pk, entity_id, id_type, id_value, mconf, mmethod],
        )


def _export_relationships(con: duckdb.DuckDBPyConnection, out: sqlite3.Connection,
                          entity_ids: Dict[str, str]) -> Dict[str, str]:
    """Assign stable relationship ids; return {rel_key -> db_id}."""
    id_map: Dict[str, str] = {}
    for (rel_key, src, tgt, rtype, conf, last_verified, status, qualifier,
         detail_type, detail_payload, detail_ver) in con.execute(
        "SELECT rel_key, source_entity_id, target_entity_id, type, confidence, "
        "last_verified, status, qualifier, detail_type, detail_payload, "
        "detail_schema_version FROM stg_relationships"
    ).fetchall():
        db_id = rel_db_id(rel_key)
        id_map[rel_key] = db_id
        out.execute(
            "INSERT INTO relationships (id, source_entity_id, target_entity_id, "
            "type, confidence, last_verified, status, qualifier, detail_type, "
            "detail_payload, detail_schema_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [db_id, entity_ids[src], entity_ids[tgt], rtype, conf,
             _dstr(last_verified), status, qualifier, detail_type,
             detail_payload, detail_ver],
        )
    return id_map


def _export_sources(con: duckdb.DuckDBPyConnection, out: sqlite3.Connection) -> None:
    for (source,) in con.execute(
        "SELECT DISTINCT source FROM stg_source_documents"
    ).fetchall():
        out.execute(
            "INSERT INTO sources (id, name, source_official) VALUES (?, ?, ?)",
            [source, schema.SOURCE_NAMES.get(source, source), 1],  # v1: all official
        )


def _export_source_documents(con: duckdb.DuckDBPyConnection,
                             out: sqlite3.Connection) -> Dict[str, str]:
    """Dedupe on fingerprint; return {doc_fingerprint -> db_id}."""
    id_map: Dict[str, str] = {}
    for fp, source, doc_type, filing_date, document_id in con.execute(
        "SELECT DISTINCT doc_fingerprint, source, doc_type, filing_date, document_id "
        "FROM stg_source_documents"
    ).fetchall():
        if fp in id_map:  # identical document reached via >1 provenance record
            continue
        db_id = doc_db_id(fp)
        id_map[fp] = db_id
        out.execute(
            "INSERT INTO source_documents (id, source_id, doc_type, filing_date, "
            "document_id) VALUES (?, ?, ?, ?, ?)",
            [db_id, source, doc_type, _dstr(filing_date), document_id],
        )
    return id_map


def _export_access_links(con: duckdb.DuckDBPyConnection, out: sqlite3.Connection,
                         doc_ids: Dict[str, str]) -> None:
    pk = 0
    seen = set()
    for fp, tier, location, row_id in con.execute(
        "SELECT DISTINCT doc_fingerprint, tier, location, row_id "
        "FROM stg_access_links"
    ).fetchall():
        doc_id = doc_ids[fp]
        dedupe_key = (doc_id, tier, location, row_id)
        if dedupe_key in seen:  # union links across duplicate docs
            continue
        seen.add(dedupe_key)
        pk += 1
        out.execute(
            "INSERT INTO access_links (id, source_document_id, tier, location, row_id) "
            "VALUES (?, ?, ?, ?, ?)",
            [pk, doc_id, tier, location, row_id],
        )


def _export_provenance(con: duckdb.DuckDBPyConnection, out: sqlite3.Connection,
                       entity_ids: Dict[str, str], rel_ids: Dict[str, str],
                       doc_ids: Dict[str, str]) -> None:
    pk = 0
    for (prov_idx, record_type, target_type, target_id, fp, anchor_type,
         anchor_payload, anchor_ver, method, code_sha, conf,
         raw_row, created_at) in con.execute(
        "SELECT prov_idx, record_type, target_type, target_id, doc_fingerprint, "
        "anchor_type, anchor_payload, anchor_schema_version, extraction_method, "
        "extraction_code_sha, confidence, raw_source_row, created_at "
        "FROM stg_provenance ORDER BY prov_idx"
    ).fetchall():
        pk += 1
        out.execute(
            "INSERT INTO provenance (id, record_type, target_type, target_id, "
            "source_document_id, anchor_type, anchor_payload, anchor_schema_version, "
            "extraction_method, extraction_code_sha, confidence, raw_source_row, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [pk, record_type, target_type,
             _remap_target(target_type, target_id, entity_ids, rel_ids),
             doc_ids[fp], anchor_type, anchor_payload, anchor_ver, method,
             code_sha, conf, raw_row, _dstr(created_at)],
        )


def _export_domains(con: duckdb.DuckDBPyConnection, out: sqlite3.Connection,
                    entity_ids: Dict[str, str]) -> None:
    seen = set()
    for domain, entity_key, is_subbrand in con.execute(
        "SELECT DISTINCT domain, entity_key, is_subbrand FROM stg_domains"
    ).fetchall():
        if domain in seen:  # domain is PK
            continue
        seen.add(domain)
        out.execute(
            "INSERT INTO domains (domain, entity_id, is_subbrand) VALUES (?, ?, ?)",
            [domain, entity_ids[entity_key], 1 if is_subbrand else 0],
        )


def _remap_target(target_type: str, target_id: str,
                  entity_ids: Dict[str, str], rel_ids: Dict[str, str]) -> str:
    """Provenance target_id: natural key -> assigned DB id (per target_type)."""
    if target_type == "relationship":
        return rel_ids.get(target_id, target_id)
    if target_type in ("entity", "entity_attribute", "external_id"):
        return entity_ids.get(target_id, target_id)
    return target_id


def _dstr(value) -> str | None:
    """date/datetime -> isoformat string for SQLite (DuckDB hands back py objects)."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _counts(out: sqlite3.Connection) -> Dict[str, int]:
    return {t: out.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in schema.PRODUCTION_TABLES}
