# Architecture Decision Records

Append-only log of decisions made building this project — architecture, data
model, scope, process. Exists to answer "why was it done this way?" for future
maintainers and contributors.

## Conventions

- **Append-only.** Historical entries are never edited. A reversal is a new
  entry that references the entry it reverses.
- **ADR numbers** are permanent IDs, assigned in append order. **Dates** are
  decision dates. The two can diverge — e.g. ADR-0008 records a 2026-05-17
  decision that was appended after the 2026-05-19 entries.
- Promoted from an internal design journal on 2026-05-20 (see ADR-0009).

## Entry format

```
## ADR-NNNN — YYYY-MM-DD — Title
**Status:** Accepted | Superseded by ADR-NNNN
**Decision:** what was decided
**Context:** why this came up
**Alternatives considered:** options not chosen + why
**Implications:** what this constrains / enables downstream
**Reverses:** (if applicable) link to entry or doc being reversed
```

---

## ADR-0001 — 2026-05-16 — Project framed as a learning vehicle
**Status:** Accepted
**Decision:** This project will be worked through as a deliberate learning exercise in data science + Python, not optimized for fastest shipping. Workflow: plan together, owner codes solo, Claude reviews after. Two glossaries (generic + project). Concept map + unknown-unknowns list maintained as scaffolds for owner's stated weak spots (can't-name-what-to-search-for, weak note-taking).
**Context:** Owner is a software dev with passing DS/Python familiarity. Wants the conceptual map to stick, not just the artifact.
**Alternatives considered:** Claude-drives-build (faster, weaker retention); pair-coding throughout (medium); read-then-extend (skim risk). Rejected — owner picked solo-after-planning explicitly.
**Implications:** Slower delivery. Heavier docs scaffold under `_human/`. Claude must not volunteer code mid-task. Per-stage cadence: landscape → owner design → review → solo code → review/compare.

## ADR-0002 — 2026-05-16 — Add Jupyter to stack for exploration
**Status:** Accepted
**Decision:** Add Jupyter notebooks to the stack for exploration / scratch work. Output pipeline remains plain Python + Makefile.
**Context:** Owner is new to DS tooling; jupyter is the standard scratch surface and a transferable skill. Stack list in CLAUDE.md previously omitted it.
**Alternatives considered:** Stay notebook-free (less DS-idiomatic, fewer transferable skills); use jupyter for the whole pipeline (rejected — notebooks are bad for reproducible pipelines).
**Implications:** `notebooks/` dir likely needed. Notebooks for exploration only, not as pipeline stages. CLAUDE.md stack section needs updating.

## ADR-0003 — 2026-05-16 — Start at the output schema, not the input
**Status:** Accepted
**Decision:** First design target is the output SQLite schema, before any parsing work.
**Context:** Two roads — design backwards from output (mature, forces entity-resolution thinking early) vs. forwards from input (tactile, but redesign-prone). Owner picked backwards.
**Alternatives considered:** Start with FCC LMS exploration (forward-from-input). Rejected for now — risks shaping the schema around what's easy to extract rather than what the output actually needs.
**Implications:** Next active task = output schema design. FCC LMS exploration deferred until schema constrains what we need to extract.

## ADR-0004 — 2026-05-19 — Three project tenets locked
**Status:** Accepted
**Decision:** Three guiding tenets adopted as project axioms.
1. **"It's just people."** Trace ownership chains toward natural persons via official sources. Where official trail dies, say so (trail-end honest). Unofficial extensions allowed only when explicitly labeled and out-of-scope for v1.
2. **Radical transparency.** Project is open source. Git history of pipeline repo = part of the data product, not internal hygiene. Design-journal + commit messages = audit trail for data-affecting decisions. We can't disparage opacity in our subjects while obscuring our own process.
3. **Extreme sourcing.** Every emitted fact links back to the most-granular official source available. Not "13F filing X" — link to *that table row*. Cross-DB combination and primary-source anchoring are co-equal pipeline goals, captured on the same record.
**Context:** Tenets articulated by owner while discussing seed-map plan. Surfaces the project's why: the subject is media opacity; the method cannot itself be opaque. "It's just people" reframes goal of the graph (people, not corporate boxes). "Extreme sourcing" sets provenance bar above typical aggregation pipelines.
**Alternatives considered:** Looser provenance ("source = filing-level URL") — rejected; loses the row-level honesty owner wants. Closed-source for early iteration — rejected; conflicts with transparency tenet.
**Implications:** Schema must support granular source anchors (row/section/page/cell where source publisher allows). Provenance is first-class table (already in `data-model.md` — confirmed). Source-tier field needed to distinguish official-direct vs official-derived vs (future) llm/unofficial. Repository hygiene matters more than typical (no rebase squashes that erase data-decision attribution).

## ADR-0005 — 2026-05-19 — v1 = automation-first, official-sources-only, no LLM
**Status:** Accepted
**Decision:** v1 pipeline restricted to standard automation against official structured data sources. **No LLM extraction in v1.** **No unofficial sources in v1** unless absolutely necessary (and labeled distinctly when admitted). Automation-first rule: even when manual data entry would be faster, automate.
**Context:** Direct corollary of Tenets 1 + 3. Hard divide between automated-on-official vs LLM/human-curated. Owner explicit: prove the automation works before any softer extraction admitted.
**Alternatives considered:** Keep LLM as second-pass fallback for malformed proxy tables (prior CLAUDE.md stack position) — deferred to v2; v1 must demonstrate official-source reach honestly first. Allow seed map data to ship as `human-curated` tier — rejected; seed map demoted to test fixture / verification ledger only.
**Implications:** CLAUDE.md stack section needs update (Anthropic API line currently lists LLM fallback). Coverage shrinks vs prior plan — accepted as honest cost. Seed map (`seed_map.json`) becomes scaffolding/fixtures only; pipeline must independently re-derive every fact from official extraction before emit. Approach: seed entry guides where to look, official extraction is what ships. Future v2 may admit `llm-extracted` and `unofficial-labeled` tiers via the source-tier field, but never silently mixed with official-direct.

## ADR-0006 — 2026-05-19 — v1 scope reframed: 1-per-category, iterative expansion
**Status:** Accepted
**Decision:** Phase 1 coverage target replaced. Old target: ~100 outlets / 18 anchor parent entities. New target: one outlet per category, owner-picked after reach/audience research. Expansion = iterative — test → fix → next → repeat. Exit on coverage ("most of American media") OR structural completion ("pipeline does what pipeline does").
**Reverses:** Prior Phase 1 framing in `_model/scope.md` and `_model/seed-anchors.md` (100 outlets / 18 anchors / 3-tier build order). Those files rewritten in place per `philosophy.md` reframe-tolerance rule.
**Context:** Owner reframed seed strategy mid-conversation. End-goal of project = user pastes any local news article URL → system identifies outlet → queries all official sources → summarized answer persisted to DB. Bulk-extract-100 was the wrong shape for that. Right shape: a small prove-out that exercises every extractor + traversal path, then expand outward.
**Alternatives considered:** Keep 18-anchor plan + add end-goal as Phase 2 — rejected; the 100-outlet target locks in a bulk-fetch mindset that conflicts with traversal-first arch needed for end-goal. Single-outlet-end-to-end (only one outlet v1) — rejected; doesn't exercise cross-category extraction differences.
**Categories** (owner picks one outlet per, after research):
- Public-co broadcast TV network (Disney/ABC, Paramount/CBS, Comcast/NBC, Fox)
- Cable news / no-FCC-license (Fox News, CNN, MSNBC)
- Public-co newspaper / digital (NYT, WSJ, Gannett)
- Private newspaper (WaPo, Cox, Hearst) — included v1 to expose obscurity-as-data
- Local TV / station group (Sinclair, Nexstar, Gray)
- Radio (iHeart, Cumulus, Audacy) — *conditional: include if cheap*
- Nonprofit news (NPR, PBS, ProPublica) — *conditional: include if difficulty doesn't spike*
**Implications:** `_model/scope.md` rewritten. `_model/seed-anchors.md` rewritten (becomes "starter outlets" doc). INV-18 rewritten. Build order shifts from "anchors first" to "one outlet, full traversal, repeat". "Pipeline done" defined structurally (all v1 extractors + traversal + provenance + export working), separate from coverage axis.

## ADR-0007 — 2026-05-19 — Modular architecture: per-source extractors + traversal layer
**Status:** Accepted
**Decision:** Three-layer architecture:
- **Layer 1 — Source extractors.** Independent Python modules per data source (FCC LMS, SEC EDGAR, IRS 990 XML, …). Each owns its source's quirks. Common return contract: `(entities[], relationships[], provenance[], coverage_log)`. Each extractor emits raw source rows alongside canonical pipeline shape, both retained.
- **Layer 2 — Resolution / traversal.** Orchestrator. Implements the `domain → entity → parent → ultimate-parent → subsidiaries` walk. Calls extractors per traversal step. Doesn't know source internals. Same layer serves v1 (script feeds starter outlet list) and end-goal (server feeds URL-derived outlet identifier). Build now, even though v1 only invokes it from a script.
- **Layer 3 — Stage / resolve / export.** Shared. DuckDB staging tables (extractor output, common schema). Cross-source entity resolution + dedupe. Validation. SQLite export (idempotent).
**Context:** Architecture question: monolith vs per-category vs modular. Per-category rejected (category is wrong axis — outlets cross categories, source is the right axis: Comcast's broadcast+cable+digital all use the same SEC+FCC paths). Monolith rejected (each new source = surgery on every stage). Modular chosen, owner-leaned.
**Alternatives considered:** Per-stage plugin model (per-pipeline-stage plugins instead of per-source extractors) — overkill at 3 sources. Event-sourced facts table (immutable event log, current state = projection) — useful for end-goal write-back, deferred to v2.
**Implications:**
- Extractor contract is the only required abstraction. Three Python modules + a registry. No base class hierarchy.
- Traversal layer makes "private newspaper obscurity" near-free: iterate extractors, log "0 results" per source, emit trail-end. Architecturally identical to NYT — just empty results. Strengthens case for including private-newspaper category v1.
- End-goal flow (URL → answer) is not a re-architecture later. Same Layer 2, new entry point (server-driven instead of script-driven).
- Raw-row retention costs disk, buys auditability + Tenet 3 provenance anchors.
- `_model/data-model.md` extended with architecture section + provenance-tier fields.

## ADR-0008 — 2026-05-17 — Treat FCC schema PDFs as reference, not authority
**Status:** Accepted
**Decision:** `LMSchema.pdf` + `LM-ERD.pdf` are reference material only. Ground truth = the bulk `.dat` shape, verified empirically. Schema design draws from data probes + ERD cross-reference, never ERD-first.
**Context:** Both PDFs landed in `unfiltered_data/` alongside the bulk LMS dump. Prior guidance in `_model/data-sources.md` said `"READ BEFORE PARSING"` — that line predates discovery and is reversed by this entry. Discovery already found 14 fragility hits via OPIF API probe that the ERD wouldn't expose: sentinel-null variants (`"NO FRN"`, `"N/A"`), duplicate-row artifacts at the application layer, name-change-under-stable-FRN as a corporate event, free-text suffix encoding (`"DEBTOR-IN-POSSESSION"`), `SEE EXHIBIT` placeholder rows, M:N FRN↔entity. Published schemas describe intent; bulk data shows extraction reality, including legacy CDBS→LMS migration artifacts (2013 cutover).
**Alternatives considered:** Trust ERD as authoritative (cheap, fast — rejected; schemas-on-paper diverge from operational data, especially across legacy migrations). Skip ERD entirely (rejected; cheap reference for column-name canonicalization, enum hints, FK shape).
**Implications:** `_model/data-sources.md` guidance line flipped. ERD usable for: column-name canon, enum candidate lists, FK structure hints. Never final word on type, fill, or semantics. Adds explicit "verify bulk-dump parity" step to FCC stage. Generalizes: same posture toward SEC/IRS bulk docs when they appear.

## ADR-0009 — 2026-05-20 — Design journal promoted to public ADR log
**Status:** Accepted
**Decision:** The internal design journal (`Project Context/_model/design-journal.md`, gitignored) is promoted in place to a git-tracked, public Architecture Decision Record log at `docs/adr.md`. Entries gain permanent numeric IDs (ADR-NNNN, append order) and an explicit `Status:` line. Content, append-only rule, and entry shape are unchanged. Process-meta entries (ADR-0001 learning vehicle, ADR-0002 jupyter) are kept — they answer real "why is the code like this?" questions a contributor will hit.
**Context:** Tenet 2 (ADR-0004) names the design journal + git history as the project's decision audit trail — but the journal lived under gitignored `Project Context/`, so no decisions were version-controlled, contradicting the tenet. The repo is open source; the operative goal is a tractable record answering "why did they do it like that?" for future maintainers, not transparency as performance.
**Alternatives considered:** (B) fork a fresh ADR series, keep the journal private for messier reasoning — rejected; splits the record. (C) hybrid — rejected; same. Carve a `.gitignore` exception for the file in place under `Project Context/` — rejected; an ADR log is no longer machine-only model context, it has graduated to a first-class doc, so it belongs in `docs/`.
**Implications:** `docs/adr.md` is now version-controlled and diffable. Hard path refs updated: `_model/INDEX.md`, `_model/maintenance.md`, `CLAUDE.md` rule 4. Narrative "see design journal" refs across `_model/*` to be swept in the D3 `_model/*` audit pass. A companion standing doc `docs/llm-use.md` (reader-facing, not append-only) will document the LLM's role across pipeline + build + research + test; a future ADR entry will lock that LLM-use policy.

## ADR-0010 — 2026-05-20 — Demote broadcast_group_map + pe_adviser_map to verification fixtures
**Status:** Accepted
**Decision:** `broadcast_group_map.json` (FCC licensee name → SEC CIK) and `pe_adviser_map.json` (PE firm name → Form ADV CRD) are removed as emitted/standing input config. Both bridge official source → official source; that mapping is derivable at runtime and must be. If kept at all, each is only a verification ledger / test fixture — the same status `seed_map.json` holds under ADR-0005 — used to validate the resolver, never to feed or short-circuit emitted output. `domain_map.json` is unaffected: it remains the one authoritative manual input (URL → entity has no official source, ever).
**Context:** Both maps cross official→official (FCC↔SEC, PE-name↔SEC ADV). FCC ownership reports already disclose the ownership chain within FCC; ultimate-parent name → SEC CIK is a lookup against SEC's published company index; PE firm → CRD is a lookup against the Form ADV bulk dataset (already downloaded). The maps were planned as hand-curated confidence-caches over a fuzzy-match step. The project's purpose is to derive everything from official sources + accumulated DB; a standing hand-curated official→official bridge contradicts that. `pe_adviser_map`'s second job — scoping which PE firms are media-relevant — also dissolves: traversal reaches a PE firm via co-occurrence (ADR-0007), it is not pre-declared.
**Alternatives considered:** Keep the maps as emitted input config (original plan in `data-sources.md` / `external/data-download-checklist.md`) — rejected; hand-curation hides from the fuzzy-match problem for the top 20 and abandons the rest, and is reference beyond official sources. Drop entirely with no fixture — rejected; known-correct top-group bridges are valuable as a resolver test oracle.
**Reverses:** Map rows in `_model/data-sources.md` describing the two maps as pipeline inputs, and the corresponding items in `external/data-download-checklist.md`. `data-sources.md` updated in place; `external/*` is canonical and not modified (INV-17) — this entry records the reversal.
**Implications:** The FCC→SEC and PE→CRD bridges become runtime resolution (see ADR-0011). The fragility (FCC free-text name swamp — 14 discovery fragility hits) does not vanish; it moves from "curate around it" to "build a robust resolver + verification harness." Consistent with ADR-0005 — the pipeline re-derives every emitted fact independently. `_model/snapshot.md` manual-inputs list updated.

## ADR-0011 — 2026-05-20 — Resolution architecture: two-layer split + extractor resolve() contract
**Status:** Accepted
**Decision:**
1. **Two distinct resolutions, never conflated.**
   - **Resolution #1 — URL → entity.** Source-agnostic. URL-normalize → `domain_map` lookup → entity. Its own pre-traversal module, called by whatever the entry point is (v1 script, post-v1 server). Layer 2 traversal always receives an entity, never a URL. Deterministic — `domain_map` is a curated dict; no ambiguity, no pick-list.
   - **Resolution #2 — entity → source-local key** (CIK / FRN / EIN). Per-source. Lives in each extractor as `resolve()`.
2. **Extractor interface gains `resolve()`** alongside `extract()` (refines ADR-0007's contract):
   - `resolve(entity) → ResolutionResult` — `{ source_key | None, confidence, candidates[], provenance, method }`.
   - `extract(source_key) → ExtractorResult` — the existing `(entities, relationships, provenance, coverage_log)` tuple.
3. **SDK-confinement.** No source-specific SDK (`edgartools`, etc.) is imported outside its own extractor module. A source SDK is a data-fetch backend, not the definition of resolution. If resolution logic needs a source SDK, it is misplaced.
4. **Shared vs per-extractor split.** Shared (Layer 2/3 / common): URL normalization, `domain_map`, name normalization + aliases + `rapidfuzz` scoring, confidence rules, the `resolve()`/`extract()` interface, DB-cache lookup. Per-extractor: the call to the source's own search/data API, mapping source records → canonical contract.
5. **Five-tier resolution outcome model** — `resolve()` result drives handling: (1) 1 match high-confidence → auto-accept; (2) small set, no clear winner (≤ ~20) → human pick-list; (3) large/unfiltered set (> ~20) → resolution failure, query/filter broken; (4) 0 matches → trail-end honest (INV-19); (5) 1 match low-confidence → flag, never silently auto-accepted.
6. **Pick-list UX deferred to post-v1.** v1 resolution: unique-confident → accept; else flag / trail-end, no human ask. `ResolutionResult.candidates[]` exists from day one so the pick-list bolts on with no refactor.
**Context:** Resolution exists for UX — users paste a URL and never look up a CIK/FRN/EIN. Owner flagged refactor risk: if entity→identifier resolution is built inside an extractor coupled to that source's SDK, adding the next source forces a rebuild. The dangerous failure is not "too many candidates" but "confidently wrong" — one high-confidence answer that is wrong silently corrupts the graph; confidence calibration + the ADR-0010 verification ledger guard this, not the pick-list.
**Alternatives considered:** Single resolver conflating both resolutions — rejected; that is the coupling. A standalone resolution service with extractors registering `find_candidates()` — cleaner separation but overkill before 3 sources; revisit if source count grows. Lean per-extractor `resolve()` chosen.
**Reverses:** Nothing outright; refines ADR-0007 (extractor contract) and `_model/entity-resolution.md`.
**Implications:** `_model/entity-resolution.md` + `_model/data-model.md` updated with the resolution model. Two new invariants (SDK-confinement, two-layer resolution split). Thresholds (the ~20 ceiling), per-source matching strategy, and exact outcome handling are **provisional — to be tuned by stress-testing the resolver against real source data**, not finalized now. A human pick-list selection is a resolution act (which official filer is this entity), not fact authoring — facts remain auto-derived from the chosen official record — so INV-10 does not block the post-v1 pick-list; it needs a provenance note on the identifier link (deferred).

## ADR-0012 — 2026-05-21 — Final pipeline directory layout
**Status:** Accepted
**Decision:** Concrete directory/module structure realizing the three-layer architecture (ADR-0011, INV-27..32):
```
pipeline/                package root (renamed from main/)
  contracts.py           shared dataclasses — Entity, Relationship,
                         ProvenanceRecord, CoverageLog, ResolutionResult,
                         ExtractorResult. Dependency-free; imported by all layers.
  resolution/            shared resolution utils — names.py (normalize +
                         rapidfuzz), urls.py (URL normalize), confidence.py
                         (score → tier). Imported by extractor resolve() AND Layer 2.
  extractors/            LAYER 1 — __init__.py = source-name → module registry
    sec/                 resolve.py, extract.py, reference/ (source-local data)
    fcc/                 stub
  traversal/             LAYER 2 — url_to_entity.py (Resolution #1), walk.py
  staging/               LAYER 3 — stage.py, dedupe.py, validate.py, export.py
  run.py                 v1 entry point
config/domain_map.json   lone authoritative manual input (INV-32)
notebooks/               Jupyter scratch — recon spikes only (ADR-0002)
Makefile                 per-stage targets
```
- **`contracts.py` standalone, not inside `resolution/` or a `core/` dir.** Pure type definitions, no logic, imported by every layer — kept as one obvious dependency-free file.
- **Dir-per-source extractors, lowercase names.** `extractors/sec/` not a flat `sec_edgar.py`. A dir holds the resolve/extract split + source-local `reference/` data + room for source-specific helpers, and reinforces SDK-confinement (INV-30). Lowercase per Python module convention.
- **Source-specific reference data lives source-local.** `company_tickers.json` (SEC ticker→CIK index) → `extractors/sec/reference/`, not the package root. Only the pipeline-global authoritative input (`domain_map.json`) sits in `config/`.
- **Layer 3 = one `staging/` package, four modules.** Not four top-level dirs — avoids a `resolution/` directory-name collision with the shared-util dir, and keeps Layer 3 cohesive.
**Context:** ADR-0011 locked the resolution architecture but left the concrete file layout open — specifically where shared resolution utils and shared contract types live. Neither belongs to an extractor or to Layer 2 alone, since both import them. This entry resolves the active "final pipeline layout" task.
**Alternatives considered:** Single `core/` dir grouping contracts + utils — rejected; contracts are dependency-free types imported universally and read clearer as a standalone file. Four top-level Layer-3 dirs — rejected; `resolution/` name clash, less cohesive. Keep `main/` as package name — rejected; non-descriptive, unconventional for a Python package. Flat per-source module files (`extractors/sec_edgar.py`, the original `data-model.md` examples) — rejected; a dir-per-source carries source-local data + multi-file extractors and strengthens SDK-confinement.
**Reverses:** `_model/data-model.md` Layer 1 examples showing flat `extractors/fcc_lms.py` / `sec_edgar.py` / `irs_990.py`.
**Implications:** `_model/data-model.md` synced (Layer 1 examples + directory-layout block + `domain_map.json` path). No new invariants — the layout is an elaboration of INV-27..32. `main/extractors/SEC/index.py` retired to `notebooks/sec_recon.py` (recon scratch, to be rewritten clean against the contract). CLAUDE.md "Run" section still TBD — Makefile targets now stubbed, recipes pending. Scaffold created: 21 docstring-only module files.

## ADR-0013 — 2026-05-21 — External-IDs child table + evidence/provenance subsystem
**Status:** Accepted
**Decision:**
1. **External IDs → child table `entity_external_ids`.** One row per `(entity_id, id_type, id_value)`. Columns: `entity_id` FK, `id_type` enum (`frn` / `cik` / `ein` / `facility_id` / `crd` / …), `id_value`, `status`. The `entities` table carries zero source identifiers. INV-1 establishes FRN as M:N to entities (Bonneville: 3 FRNs ↔ 1 entity stack; Paramount: 5 names under 1 FRN) — an M:N relationship cannot be modeled as a set of nullable columns on `entities`.
2. **Evidence subsystem — four tables, replacing single-table provenance.**
   - `sources` — the source system itself (FCC LMS, SEC EDGAR, IRS 990). ~3 rows in v1. Carries `source_official` (bool).
   - `source_documents` — one specific filing / document. Carries the filing/publication date, which feeds INV-6 `last_verified`. One document is referenced by many provenance records.
   - `access_links` — how to reach a document; **many per document**. All three tiers stored, not just the most-direct: A = public URL, B = bulk-download URL + row id, C = our hosted mirror. Mirror-everything.
   - `provenance` — per-detail grain. Binds one extracted fact to one `source_document`. Carries the anchor (decision 3), the polymorphic target (decision 4), `extraction_method`, `extraction_code_sha`, `raw_source_row`, `confidence`.
   Reference shape: `provenance → source_document → source`; `access_links → source_document`.
3. **Anchor = typed payload, not wide columns.** `provenance` carries `anchor_type` (enum the pipeline controls), `anchor_payload` (JSON), `anchor_schema_version`. Each `anchor_type` has a documented payload shape (not DB-enforced); the interpret/validate logic for a type is written per-source, when that extractor is built. The anchor is the only structurally source-divergent part of a provenance record — three-zone model: common metadata (structured columns) / source-divergent anchor (typed payload) / raw source row (opaque blob, INV-28). A new source adds an `anchor_type` value + payload shape + interpret module; existing rows untouched, no migration.
4. **Provenance target = polymorphic.** `provenance` carries `target_type` (`relationship` / `entity_attribute` / `external_id`) + `target_id`. Per-detail grain (INV-3) plus extreme sourcing (INV-26) require entity attributes and external IDs to be sourced, not only relationships.
5. **Scope split + capture-or-lose, recorded as principle.** The pipeline is *witness/capture* — it records what was seen, where, and how. The website (separate repo) is *experience* — how that is shown to a user. The provenance schema serves capture only; display concerns never shape it. **Capture-or-lose:** at extraction time the pipeline must capture everything not reliably re-fetchable later — `raw_source_row`, anchor payload, all `access_links` including the mirror, and the fetch timestamp. Access state decays (a 2021 filing's public URL may be dead in 2027); the schema must hold all of it before the first extractor runs.
**Context:** Evidence/provenance was the largest open design thread (handoff focus). The trigger: structural divergence across sources — FCC LMS `.dat`, SEC proxy HTML/XBRL, IRS 990 XML share almost no structure — and owner's concern that a fixed provenance schema would either fail future/unofficial sources or force premature over-generalization. Resolved by separating provenance into three zones by divergence: only the anchor (the in-document locator) is genuinely source-divergent; common metadata and the raw row are not. Generalize only the anchor; design it for the three known v1 sources; let the `anchor_type` enum carry future sources additively. Over-generalizing now pays a real, present cost (lost cross-source validation, schema drift) to insure against sources that cannot be specified — the wrong direction, since fixing too-specific later is cheap and additive while fixing too-generic is expensive.
**Alternatives considered:** N nullable identifier columns on `entities` — rejected; INV-1's M:N relationship cannot be columns. Single-table provenance (prior `data-model.md` design) — rejected; cannot express per-detail grain, document reuse across many facts, or multiple access tiers per document. Store only the most-direct access link (prior INV-3) — rejected; violates capture-or-lose, access state decays. Wide-nullable anchor columns (`page`/`section`/`xpath`/`text_snippet`, the original ADR-0013 draft) — rejected; grows a NULL column per new source, the over-generalization trap in column form. Blob the entire provenance record behind a type discriminator — rejected; would bury `extraction_method`, tier, and dates that cross-source validation (INV-11) and the answer card must read uniformly.
**Reverses:** INV-3 "prefer most-direct link" → all access tiers stored (decision 2). INV-3 anchor shape "row/section/XPath/PK" → typed payload (decision 3). Supersedes the single-table `provenance` design in `_model/data-model.md`.
**Implications:** New invariants needed — external-IDs child table; four-table evidence subsystem; anchor typed-payload; all-access-tiers-stored; capture-or-lose; polymorphic provenance target. INV-3 to be rewritten for all-tiers + typed anchor. `_model/data-model.md` Provenance section rewritten and `entities` external-IDs row removed (done this session). `_model/invariants.md` + `_model/handoff.md` sync still pending. `pipeline/contracts.py` unblocked — `ProvenanceRecord` plus `Source`, `SourceDocument`, `AccessLink`, `ExternalId` dataclasses now finalizable against the locked schema. Per-`anchor_type` payload shapes are documented when each extractor is built, not specified here; v1 set = FCC LMS / SEC EDGAR / IRS 990.
