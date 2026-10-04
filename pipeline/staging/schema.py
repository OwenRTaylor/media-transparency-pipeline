"""Layer 3 schema — DuckDB staging DDL + production SQLite DDL, in one place.

Two schemas live here so stage.py and export.py can't drift:

* **Staging (DuckDB)** — a flat mirror of the in-memory contract objects
  (`pipeline/contracts.py`). One row per emitted object, keyed by the
  *natural* keys the extractor can produce (entity id/slug, relationship
  natural key, document fingerprint). No cross-object id assignment yet —
  that is export's job. JSON-shaped fields (aliases, attributes, payloads,
  raw rows) are stored as JSON strings.

* **Production (SQLite)** — the 8 locked tables (data-model.md, ADR-0013).
  Stable DB ids assigned, source_documents deduped, provenance targets
  remapped to those ids. This is the artifact the Node.js server reads.

Idempotent export (INV-12): every production table is DROP-then-CREATE.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# Staging (DuckDB). Prefix stg_. Flat, pre-id-assignment.
# --------------------------------------------------------------------------

STAGING_TABLES = (
    "stg_entities",
    "stg_external_ids",
    "stg_relationships",
    "stg_provenance",
    "stg_source_documents",
    "stg_access_links",
    "stg_domains",
)

STAGING_DDL = """
CREATE TABLE stg_entities (
    entity_key      TEXT,          -- extractor-provided id/slug ("" if unresolved)
    type            TEXT,
    canonical_name  TEXT,
    aliases         JSON,
    attributes      JSON,
    domains         JSON,
    raw_source_row  JSON
);

CREATE TABLE stg_external_ids (
    entity_key       TEXT,
    id_type          TEXT,
    id_value         TEXT,
    merge_confidence TEXT,         -- NULL = native to entity's own source
    merge_method     TEXT
);

CREATE TABLE stg_relationships (
    rel_key               TEXT,    -- natural key: source_entity_id|target_entity_id|type
    source_entity_id      TEXT,
    target_entity_id      TEXT,
    type                  TEXT,
    confidence            TEXT,
    last_verified         DATE,
    status                TEXT,
    qualifier             TEXT,
    detail_type           TEXT,
    detail_payload        JSON,
    detail_schema_version INTEGER
);

CREATE TABLE stg_source_documents (
    doc_fingerprint       TEXT,    -- dedupe key (see export._doc_fingerprint)
    source                TEXT,
    doc_type              TEXT,
    filing_date           DATE,
    document_id           TEXT
);

CREATE TABLE stg_access_links (
    doc_fingerprint  TEXT,
    tier             TEXT,
    location         TEXT,
    row_id           TEXT
);

CREATE TABLE stg_provenance (
    prov_idx              INTEGER,  -- stable order of emission
    record_type           TEXT,
    target_type           TEXT,
    target_id             TEXT,     -- natural key (rel_key / entity_key / external-id key)
    doc_fingerprint       TEXT,     -- link to the embedded source_document
    anchor_type           TEXT,
    anchor_payload        JSON,
    anchor_schema_version INTEGER,
    extraction_method     TEXT,     -- NULL for gaps
    extraction_code_sha   TEXT,
    confidence            TEXT,     -- NULL for gaps
    raw_source_row        JSON,
    created_at            TIMESTAMP
);

CREATE TABLE stg_domains (
    domain       TEXT,
    entity_key   TEXT,
    is_subbrand  BOOLEAN
);
"""

# --------------------------------------------------------------------------
# Production (SQLite). The 8 locked tables. Drop + recreate each run.
# --------------------------------------------------------------------------

PRODUCTION_TABLES = (
    "entities",
    "entity_external_ids",
    "relationships",
    "sources",
    "source_documents",
    "access_links",
    "provenance",
    "domains",
)

PRODUCTION_DDL = """
CREATE TABLE entities (
    id             TEXT PRIMARY KEY,
    type           TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    aliases        TEXT,           -- JSON array
    attributes     TEXT            -- JSON object
);

CREATE TABLE entity_external_ids (
    id               INTEGER PRIMARY KEY,
    entity_id        TEXT NOT NULL REFERENCES entities(id),
    id_type          TEXT NOT NULL,
    id_value         TEXT NOT NULL,
    merge_confidence TEXT,         -- set only for cross-source merges (else NULL)
    merge_method     TEXT,
    UNIQUE(entity_id, id_type, id_value)
);

CREATE TABLE relationships (
    id                    TEXT PRIMARY KEY,
    source_entity_id      TEXT NOT NULL REFERENCES entities(id),
    target_entity_id      TEXT NOT NULL REFERENCES entities(id),
    type                  TEXT NOT NULL,
    confidence            TEXT NOT NULL,     -- INV-9: never NULL
    last_verified         TEXT,              -- source filing date (INV-6)
    status                TEXT NOT NULL,
    qualifier             TEXT,
    detail_type           TEXT,
    detail_payload        TEXT,              -- JSON
    detail_schema_version INTEGER
);

CREATE TABLE sources (
    id              TEXT PRIMARY KEY,        -- source system key, e.g. "sec_edgar"
    name            TEXT,
    source_official INTEGER NOT NULL         -- two-axis tier; v1 always 1
);

CREATE TABLE source_documents (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL REFERENCES sources(id),
    doc_type    TEXT,
    filing_date TEXT,
    document_id TEXT
);

CREATE TABLE access_links (
    id                 INTEGER PRIMARY KEY,
    source_document_id TEXT NOT NULL REFERENCES source_documents(id),
    tier               TEXT NOT NULL,        -- A / B / C
    location           TEXT NOT NULL,
    row_id             TEXT
);

CREATE TABLE provenance (
    id                    INTEGER PRIMARY KEY,
    record_type           TEXT NOT NULL,     -- extraction / gap
    target_type           TEXT NOT NULL,     -- relationship / entity_attribute / external_id / entity
    target_id             TEXT NOT NULL,     -- assigned DB id of the target
    source_document_id    TEXT NOT NULL REFERENCES source_documents(id),
    anchor_type           TEXT NOT NULL,
    anchor_payload        TEXT,              -- JSON
    anchor_schema_version INTEGER,
    extraction_method     TEXT,              -- NULL for gaps; v1 always "automated"
    extraction_code_sha   TEXT,
    confidence            TEXT,              -- NULL for gaps (INV-9)
    raw_source_row        TEXT,              -- JSON, verification backup only (ADR-0015)
    created_at            TEXT NOT NULL
);

CREATE TABLE domains (
    domain      TEXT PRIMARY KEY,
    entity_id   TEXT NOT NULL REFERENCES entities(id),
    is_subbrand INTEGER NOT NULL DEFAULT 0
);
"""

# Human-readable source-system names for the derived `sources` table.
SOURCE_NAMES = {
    "sec_edgar": "SEC EDGAR",
    "fcc_lms": "FCC LMS",
    "irs_990": "IRS 990 (TEOS)",
}
