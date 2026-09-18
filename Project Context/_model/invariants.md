# Invariants

Project-wide constraints. Active at all times. Treat as binding unless explicitly reversed via design-journal entry.

## Schema (output SQLite)
1. Entities have stable unique IDs — **never name-as-ID, never FRN-as-ID**. Names change (Paramount FRN: 5 SPAC-shell names); FRNs are M:N to entities (Bonneville: 3 FRNs ↔ 1 entity stack). Both break the entity-event graph.
2. Relationships are first-class objects w/ type, confidence, provenance, last_verified, status — NOT just FKs.
3. Every relationship has ≥1 provenance record. **Granular sourcing (Tenet 3):** each provenance record binds to one `source_document` and carries a typed anchor (`anchor_type` + `anchor_payload` + `anchor_schema_version`), `extraction_code_sha`, and `raw_source_row`. Three access-link tiers — A=public URL, B=bulk-download URL + row id, C=our hosted mirror — stored per document; **all reachable tiers captured, not only the most-direct** (capture-or-lose; ADR-0013 reverses prior "prefer most-direct"). Two-axis tier: `source_official` (bool) × `extraction_method` (`automated`/`llm`/`human-curated`). See INV-33..38.
4. Relationship taxonomy distinguishes: `direct_ownership` ≠ `parent_company` ≠ `family_control` ≠ `major_shareholder` ≠ `private_equity` ≠ `nonprofit_funding` ≠ `trust_structure` ≠ `governance` ≠ `unknown_opaque`. Never flatten.
5. `governance` (nonprofit board) is NOT ownership. Different display.
6. `last_verified` = source filing date, not pipeline run date.
7. Domain mapping is INPUT (`domain_map.json`), not derived.

## Pipeline
8. **Automation-first.** Seed map = test fixture / verification ledger only, NOT emitted data. `seed_map.json` holds starter outlet identifiers + owner-verified ground-truth used to validate extractor output. Pipeline re-derives every emitted fact from official extraction independently. Even when manual entry would be faster, automate. (Reframes prior INV-8 — see design journal 2026-05-19.)
9. Confidence assignment is mandatory per relationship. No NULL confidence.
10. **v1 = no LLM extraction, no unofficial sources.** Standard automation against official structured data only. LLM and unofficial sources reserved for v2+ via two-axis tier field; never silently mixed with official-direct.
11. Validation runs after every stage. Fail → flag for manual review, not silent drop.
12. Export idempotent: drop + recreate all tables each run.
13. Pipeline (Python) and server (Node.js, separate repo) communicate via SQLite file. No shared runtime.
14. Bulk-data over live API. Cold-path SEC/FCC live queries = NOT in Phase 1.

## Data handling
15. Never `Read` whole on bulk data (`*.zip`, `*.xml`, `*.csv` over ~10 MB). Use grep slice, head/tail, or streaming script.
16. SEC filing fetches: 10 req/sec + `User-Agent` header w/ contact email.
17. Original `external/*.md` files = canonical source. Never modify. Compress into `_model/*` instead.

## Scope (Phase 1)
18. **v1 seed = 1 outlet per category** (owner-picked after reach/audience research). Categories: public-co broadcast TV net, cable news, public-co newspaper/digital, private newspaper, local TV/station group; radio + nonprofit conditional. Expansion iterative — test → fix → next. Exit on coverage ("most of American media") OR structural completion ("all v1 extractors + traversal + provenance + export working"). International + creator economy + podcasts + temporal = OUT. (Reframes prior INV-18 — see design journal 2026-05-19.)
19. Trail-end honest: "trail ends at X — no further records" is valid output, not failure.
20. Murkiness visible. Opaque structures must surface as opaque, not as empty. **Private newspaper category included v1 specifically to expose obscurity-as-data.**

## Discovery-phase additions (merged 2026-05-17)
21. **Stage-time dedupe** by `(applicationId, partyName, applicantFrn)`. Source dupes 2–8× same row in OPIF responses; verify bulk LMS dump at stage-2 ingestion. [extends Pipeline]
22. **Name-change-under-stable-FRN = `corporate_event` record**, not extraction error. Emit w/ timestamp + old/new name. Examples: Paramount SPAC merger shells, ABC 5-name history under one FRN. [extends Schema]
23. **Parser specialization at anchor-parent granularity, not category.** Same parent → same shape (KFI≈WHTZ; WSB≈KIRO). Same category → divergent (KCBS≠WABC). Diminishing returns past ~2 samples per parent. [extends Pipeline]

## Tenets (merged 2026-05-19)
24. **"It's just people."** Traversal goal = natural persons via official sources. Trail-end honest where chain dies; unofficial extensions excluded from v1.
25. **Radical transparency.** Open source. Git history + design-journal = audit trail for data-affecting decisions. No rebase squashes that erase data-decision attribution.
26. **Extreme sourcing.** See INV-3. Every emitted fact links back to the most-granular official source row available.

## Architecture (locked 2026-05-19)
27. **Modular three-layer.** Layer 1 = per-source extractors (FCC, SEC, IRS, …) w/ common return contract `(entities, relationships, provenance, coverage_log)`. Layer 2 = resolution/traversal (domain → entity → parent → ultimate parent → subsidiaries; gap-detection from co-occurrence). Layer 3 = shared staging + dedupe + validation + SQLite export. Source = axis of decomposition, not outlet category. Extractors never call other extractors; cross-source logic in Layer 2 only.
28. **Raw + canonical retention.** Each extractor emits raw source row alongside canonical entity/relationship shape. Both kept. Raw row = Tenet 3 audit anchor.
29. **End-goal-ready traversal.** Layer 2 callable from script (v1) and from server (post-v1 URL → answer flow). Same code, different entry point. Not a re-architecture later.

## Resolution (locked 2026-05-20, ADR-0011)
30. **SDK-confinement.** No source-specific SDK (`edgartools`, etc.) imported outside its own `extractors/<source>/` module. Source SDK = data-fetch backend, not the definition of resolution. [extends Architecture]
31. **Two-layer resolution.** Resolution #1 (URL→entity) = source-agnostic, pre-traversal, deterministic `domain_map` lookup; Layer 2 receives an entity, never a URL. Resolution #2 (entity→source-key) = per-extractor `resolve()` returning `ResolutionResult{source_key|None, confidence, candidates[], provenance, method}`. Never conflate the two. [extends Architecture]
32. **Routing maps that bridge official→official must be derived, not curated.** Only `domain_map.json` is authoritative manual input (URL→entity has no official source). `broadcast_group_map.json` / `pe_adviser_map.json` = verification fixtures only, never emitted (ADR-0010). [extends Pipeline]

## Evidence / provenance (locked 2026-05-21, ADR-0013)
33. **External IDs in `entity_external_ids` child table** — one row per `(entity_id, id_type, id_value)`. Never identifier columns on `entities`; FRN↔entity is M:N (INV-1). [extends Schema]
34. **Evidence = four tables.** `sources` (system) → `source_documents` (one filing) → `provenance` (per-detail fact binding); `access_links` (M per document). No single-table provenance. [extends Schema]
35. **All access-link tiers stored**, never only the most-direct. Access state decays — mirror-everything at extraction time. Revises INV-3. [extends Schema]
36. **Anchor = typed payload** — `anchor_type` (pipeline-controlled enum) + `anchor_payload` (JSON) + `anchor_schema_version`. Never wide-nullable anchor columns. New source = additive `anchor_type`, no migration. [extends Schema]
37. **Provenance target is polymorphic** — `target_type` (`relationship`/`entity_attribute`/`external_id`) + `target_id`. Entity attributes + external IDs are sourced, not only relationships. [extends Schema]
38. **Capture-or-lose.** Pipeline = witness/capture; website = experience. At extraction time capture everything not reliably re-fetchable later (raw row, anchor payload, all access links incl. mirror, fetch timestamp, full source document to local cache). Schema serves capture; display concerns never shape it. [extends Pipeline]

## Provenance (ADR-0015, ADR-0016, ADR-0017 — locked 2026-05-30)
39. **Promote-everything.** `raw_source_row` is a verification backup only. All queryable detail promoted to structured fields — relationship `detail_payload`, entity attributes, or external IDs. The blob is never a data store. The frontend decides what to display; the pipeline captures everything cleanly. [extends Schema]
40. **Unified provenance.** Gaps (data exists but can't be extracted) are provenance records with `record_type = 'gap'`, not a separate table. One table to answer "what does the pipeline know about X?" Current state = most recent `created_at`. Gap lifecycle is append-only — when extraction fills a gap, a new `extraction` record is written; the gap record stays as history. [extends Schema]
41. **Relationship typed detail.** `relationships` carries `detail_type` + `detail_payload` (JSON) + `detail_schema_version` — same pattern as provenance anchors (ADR-0013). Source-specific detail lives in the payload; universal fields (`type`, `confidence`, `status`, `last_verified`) stay as columns. [extends Schema]
42. **Document cache.** Every fetched source document cached locally in original format. Linked via `access_links` Tier C (file path). Full chain: provenance → source_document → access_link (Tier C) → file on disk. Storage layout details deferred to first extractor. [extends Pipeline]
