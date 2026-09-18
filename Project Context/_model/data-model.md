# Data Model

Output schema = SQLite. Consumed by separate Node.js server. Pipeline + server share schema, not runtime.

## Architecture (locked 2026-05-19)

Modular, three layers. Source = axis of decomposition, not outlet category.

### Layer 1 — Source extractors
Independent Python modules per data source. Each owns its source's quirks.

Examples (v1) — dir-per-source (ADR-0012):
- `extractors/fcc/` — bulk LMS `.dat` files
- `extractors/sec/` — EDGAR proxies, 10-Ks (Exhibit 21), 13F/G/D
- `extractors/irs/` — TEOS XML (Schedule R for related orgs)

Common return contract:
```
ExtractorResult = (
  entities: list[Entity],          # canonical shape + raw source record kept
  relationships: list[Relationship],
  provenance: list[ProvenanceRecord],
  coverage_log: CoverageLog        # what was queried, found, not-found
)
```

Each extractor also exposes `resolve(entity) → ResolutionResult` — entity → its source-local key (CIK/FRN/EIN). See `entity-resolution.md` resolution architecture (ADR-0011).

Rules:
- Extractor emits **raw source row** alongside canonical entity/relationship. Raw kept for audit + Tenet 3 row-level provenance.
- No base class hierarchy. Function signature + tuple return = the only abstraction.
- New source = new module + register in extractor registry. Layer 2/3 untouched.
- Extractor never calls other extractors. Cross-source logic lives in Layer 2.

### Layer 2 — Resolution / traversal
Orchestrator. Implements:
```
domain → entity → parent → ultimate-parent → subsidiaries
```
Walks the graph by dispatching to Layer 1 extractors per traversal step. The `domain → entity` step (Resolution #1) is a source-agnostic pre-traversal module — Layer 2 itself always receives an entity, never a URL (ADR-0011).

- Upward trace: outlet → parent → grandparent → … → trail-end (parent-of disclosure across SEC + FCC + IRS).
- Downward sweep: ultimate parent → all owned media entities (SEC Exhibit 21, FCC LMS by-parent-FRN, IRS 990 Schedule R).
- Gap detection: entity appears as `target` of relationship but never reached as `source` → enqueue for sweep.
- Trail-end honest: when all extractors return empty for a step, emit `unknown_opaque` w/ coverage log showing which sources were queried.

Same layer serves:
- v1: invoked from script w/ starter outlet list
- end-goal (post-v1): invoked from server w/ URL-derived outlet identifier

No source-specific business logic in Layer 2 — only graph walk + extractor dispatch.

### Layer 3 — Stage / resolve / export
Shared, source-agnostic:
- DuckDB staging tables (extractor output, common schema).
- Cross-source entity resolution + dedupe (rapidfuzz for name matching, exact match on stable IDs).
- Validation runs after every stage. Fail → flag for manual review, not silent drop.
- SQLite export (idempotent — drop + recreate every run).


### Directory layout (ADR-0012)
```
pipeline/
  contracts.py        shared dataclasses — imported by all layers
  resolution/         shared utils — names.py, urls.py, confidence.py
  extractors/         L1 — __init__.py = registry; sec/, fcc/ (dir-per-source)
  traversal/          L2 — url_to_entity.py (Resolution #1), walk.py
  staging/            L3 — stage.py, dedupe.py, validate.py, export.py
  run.py              v1 entry point
config/domain_map.json   lone authoritative manual input
notebooks/               Jupyter recon scratch only
Makefile                 per-stage targets
```
Source-specific reference data lives source-local (`extractors/sec/reference/`).

## Tables (production SQLite)
- `entities` — nodes
- `entity_external_ids` — entity → source identifiers, M:N (ADR-0013)
- `relationships` — first-class edges
- `sources` — source systems: FCC LMS / SEC EDGAR / IRS 990 (ADR-0013)
- `source_documents` — specific filings / documents (ADR-0013)
- `access_links` — how to reach a document, all tiers (ADR-0013)
- `provenance` — per-detail evidence record (ADR-0013)
- `domains` — domain → entity mapping for URL resolution

## Entities
Anything in an ownership chain. Required:
- Stable unique ID (**critical for future entity-event graph — never use name strings as ID**)
- Canonical name
- Aliases
- Type (enum)
- External IDs (CIK, EIN, FRN, facility_id, CRD): in `entity_external_ids` child table — M:N, never columns on `entities` (ADR-0013)
- For outlets: domains (separate table)

**Types:**
| Type | Notes |
|---|---|
| Outlet | News source (brand + domains) |
| Company | Parent, holding, media group |
| Fund/InvestmentGroup | PE, hedge fund, investment firm |
| Trust/Foundation | Family trusts, foundations, endowments |
| NaturalPerson | Real human |
| Gov/Regulatory | FCC, state agencies (Phase 2 — schema must allow) |

## Relationships
**First-class objects, not FKs.** Required fields:
- source_entity_id, target_entity_id (directed)
- type (controlled taxonomy)
- confidence (high / medium / low)
- provenance: `provenance` records point to the relationship (`target_type='relationship'`, ADR-0013); a relationship is invalid without ≥1
- last_verified date (set to source filing date, not pipeline run date)
- status (active / historical / uncertain)
- qualifier (optional — e.g. "dual-class voting", "VIE consolidation")
- detail_type + detail_payload (JSON) + detail_schema_version — typed detail payload (ADR-0015). Same pattern as provenance anchors. All queryable source detail promoted here; `raw_source_row` on provenance is a verification backup only, never a data store.

**Type taxonomy (initial — small, defined; extensible):**
| Type | Meaning |
|---|---|
| `direct_ownership` | A owns B outright or controlling interest |
| `parent_company` | A is corporate parent of B |
| `family_control` | Natural person / family exercises documented control |
| `private_equity` | PE firm owns or controls |
| `major_shareholder` | Significant non-controlling (5%+ for public co per SEC) |
| `nonprofit_funding` | Foundation / nonprofit provides significant funding |
| `trust_structure` | Held through trust |
| `governance` / `board_control` | Nonprofit board (NOT ownership — display differently) |
| `unknown_opaque` | Relationship exists but type or party undeterminable from public records |

**Taxonomy rule:** never flatten "owned by" / "is major shareholder of" / "funded by" / "governed by" into one label. Card design depends on this distinction.

## Evidence / provenance subsystem (ADR-0013)

Four tables, replacing the earlier single `provenance` table. Separates the parts of "where did this come from" that are common across all sources from the one part that is genuinely source-divergent.

**Three zones by divergence:**
- Common metadata (extraction method, code SHA, dates, confidence) — identical questions every source answers → structured columns.
- Source-divergent anchor (the in-document locator) → typed payload (see Anchor below).
- Raw source row → opaque blob (INV-28).

The pipeline is *witness/capture*; the website (separate repo) is *experience*. This schema serves capture only — display concerns never shape it. **Capture-or-lose:** at extraction time, capture everything not reliably re-fetchable later (raw row, anchor payload, all access links incl. mirror, fetch timestamp). Access state decays — a 2021 filing's public URL may be dead in 2027.

### `sources`
The source system. v1: FCC LMS, SEC EDGAR, IRS 990 (~3 rows). Carries `source_official` (bool — see two-axis tier below).

### `source_documents`
One specific filing / document (a DEF 14A, an FCC ownership report, a 990 return). Carries the filing/publication date — this date, not the pipeline run date, feeds INV-6 `last_verified`. One document is referenced by many `provenance` rows.

### `access_links`
How to reach a document. **Many per document — all tiers stored, not just the most-direct:**
- Tier A — public URL
- Tier B — bulk-download URL + row id
- Tier C — local document cache (file path to original-format copy on disk). ADR-0017.

Mirror-everything: every reachable form captured at extraction time (capture-or-lose). The pipeline caches every fetched source document locally in its original format — full chain: provenance → source_document → access_links (Tier C) → file on disk.

### `provenance`
Per-detail grain. Binds one extracted fact — or a documented gap — to one `source_document`. Fields:
- `record_type` — `extraction` (extracted fact) | `gap` (data exists in source but not yet extractable). ADR-0016.
- `target_type` (`relationship` / `entity_attribute` / `external_id` / `entity`) + `target_id` — the fact this record sources, or the entity a gap pertains to. Polymorphic: entity attributes and external IDs are sourced, not only relationships. `entity` target type used for gap records.
- `anchor_type` + `anchor_payload` (JSON) + `anchor_schema_version` — the in-document locator (see Anchor below). For gaps, anchor_payload carries `{data_point, gap_reason}`.
- `extraction_method` — see two-axis tier below. NULL for gap records.
- `extraction_code_sha` — git SHA of the pipeline code that produced this extraction (reproducibility).
- `raw_source_row` — verbatim source row/record, or mirror pointer. Tenet-3 audit anchor (INV-28). Verification backup only — all queryable detail promoted to relationship `detail_payload` or entity attributes (ADR-0015).
- `confidence` — mandatory for extractions, never NULL (INV-9). NULL for gap records.
- `created_at` — pipeline run timestamp. Provenance records are immutable snapshots. Current state for a given target = most recent `created_at`. ADR-0016.

### Anchor — typed payload
The anchor is the only structurally source-divergent part of a provenance record. Not a wide set of mostly-NULL columns — a discriminated payload:
- `anchor_type` — enum the pipeline controls (e.g. `sec_accession`, `irs_990_xpath`, `fcc_lms_row`).
- `anchor_payload` — JSON; shape documented per `anchor_type`, not DB-enforced.
- `anchor_schema_version` — payload version, so extractor v1 vs v2 payloads stay distinguishable.

Interpret/validate logic for a type is written per-source, when that extractor is built. A new source adds an `anchor_type` value + payload shape + interpret module — existing rows untouched, no migration. Designed for the three v1 sources only; future/unofficial sources slot in additively.

Illustrative payload shapes (finalized per extractor, not here):
- SEC EDGAR — accession # + document index + section anchor
- IRS 990 — filename + EIN + tax year + XPath
- FCC LMS bulk — dump filename + table + primary key (or row hash if PK absent)

### Source tier (two-axis)
Orthogonal axes — future-safe for when v2 admits LLM/unofficial.

- **`source_official`** (bool): true = publisher-of-record (SEC, FCC, IRS, etc). false = aggregator / news / curator.
- **`extraction_method`** (enum): `automated` | `llm` | `human-curated`

v1 emits only `(source_official=true, extraction_method=automated)`. Any other combination = excluded from v1 output. Field exists so v2 can admit other tiers without schema migration.

## Domains
Domain → entity. Manually curated `config/domain_map.json` is INPUT. Domains table in SQLite = output.
- `nytimes.com`, `nyt.com`, `cooking.nytimes.com` → all map to NYT entity
- `theathletic.com` → NYT entity, flagged `is_subbrand: true`

URL not in domains table → "outlet not recognized" (honest answer, not failure).

## Pipeline → schema flow
Layer 1 extractors → DuckDB staging tables (per source) → Layer 2 traversal walks → Layer 3 entity resolution + dedupe → write production SQLite. See **Architecture** section above for layer details.

**Export is idempotent.** Drops + recreates all tables on each run. SQLite file = artifact, versioned by pipeline run date + pipeline-code git SHA.

## Invariants (enforced via validation)
- Every entity: canonical_name not NULL / empty
- Every relationship: confidence not NULL
- Every relationship: ≥1 provenance record
- No orphan relationships (source / target must exist)
- No self-referential (source = target)
- No duplicates (same source + target + type)
- `last_verified` not future-dated, not older than 36 months for active
- Every `access_link` URL syntactically valid
- Every outlet entity: ≥1 relationship
- Every domain in `domain_map.json`: resolves to valid entity
- Every seed_map entity: created in DB

## Concentration sanity
- Top 5 entities by station count match known broadcast groups
- Total stations within 10% of FCC published total
- No single entity has implausibly high % unless known major group

## Diff report
Each pipeline run → human-readable diff vs prior run. Short diff = quarterly FCC. Long diff = annual SEC+IRS. Unexpectedly large diff = signal that parsing / resolution broke.
