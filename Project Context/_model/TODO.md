# TODO — Deferred Design Work

Append-only. Each entry = problem + shape of solution + decision points. No timeline. Pull from this when ready.

---

## 2026-05-17 — Public provenance for design reasoning (open-source release prep)

**Problem.** Project is transparency tool, will be open-sourced. Best provenance of design thinking lives in `Project Context/`, which is gitignored because it contains:
- Personal info (learning context, owner personal/learning profile, owner workflow protocols)
- Owner-specific session scaffolding (handoff, learning glossary, stage notes)
- LLM-context risk: if someone forks repo + reuses Project Context as-is, their LLM gets owner-specific protocol injected (caveman mode, learning frame, owner-codes-solo rule).

Without published provenance, "why does this edge exist / why this threshold / why this label" is invisible to downstream users + future contributors. Transparency tool without its own transparency = bad faith.

**Shape (3 layers).**

1. **Split Project Context by audience, not by folder.**
   - *Public — project doctrine:* architecture, schema, taxonomy, data-source notes, invariants, design decisions, project glossary. Most existing `_model/*` already public-safe (data-sources, entity-resolution, data-model, seed-anchors, philosophy, scope).
   - *Public — neutered LLM-context:* project-only `CLAUDE.md` equivalent. Rules about project, not about owner.
   - *Private:* learning workflow, owner personal/learning notes, owner profile, session scaffolding (`handoff.md`, `_human/anytype.md`, parts of `INDEX.md`), `_human/Stage Notes/*` raw thinking.

2. **ADRs (Architecture Decision Records) = primary public provenance trail.**
   - One file per decision. Format: Context / Decision / Reasoning / Consequences.
   - Append-only. Reversals = new ADR referencing old.
   - Existing `_human/Design Journal.md` already uses similar pattern — decide: sanitize + publish as ADRs, or fork public ADR series + keep journal private for messier reasoning.

3. **Data-decision provenance ≠ architecture provenance.**
   - *Code-level* (confidence thresholds, match-rule weights, taxonomy boundaries): inline in code + linked ADR.
   - *Per-entity calls* (seed_map entries, "this PE firm controls this paper"): `rationale` field IN the data record. Each `seed_map.json` row gets `rationale` + `source_url` + `decided_by` + `decided_date`. This is *the* transparency feature — users querying SQLite output can ask "why does this edge exist?" and get human reasoning, not just provenance URL.

**LLM-mislead concern (separate fix).**
- Split `CLAUDE.md`: project rules → public. Workflow rules (caveman, learning frame) → `CLAUDE.local.md` (gitignored).
- Public README warns: "`Project Context/_doctrine/` is intentionally LLM-readable. Don't add your own profile; use `CLAUDE.local.md`."

**Decision points (owner).**
1. ADR adoption — yes/no. Extend existing Design Journal or fresh series?
2. Rationale-in-data — confirm pattern applies to `seed_map.json`, `domain_map.json`, `broadcast_group_map.json`, `pe_adviser_map.json`.
3. Audit pass on `_model/*` — flag what's owner-personal vs project-doctrine. Produces diff/checklist of publish-as-is / strip / move.
4. `CLAUDE.md` split — when.

**Pickup hint.** Item 3 (audit pass) = mechanical, can be done by Claude on owner ask. Items 1-2-4 = owner design decisions, do those first.

---

## 2026-05-20 — Resolves 2026-05-17 provenance entry (partial)

Status of the 4 decision points above:
1. **ADR adoption — DONE.** Promoted in place to `docs/adr.md` (git-tracked). See ADR-0009.
2. **Rationale-in-data — collapsed.** `broadcast_group_map` + `pe_adviser_map` demoted (ADR-0010) → not emitted, no rationale-to-ship. Pattern now applies to `domain_map.json` only. **Still open:** field shape — `rationale` required-vs-optional, `source_url` nullable, `decided_by` enum. `seed_map.json` rationale handled in fixture workflow.
3. **`_model/*` audit (D3) — PENDING.** Still to do. Adds: rename narrative "see design journal" refs → ADR; reconcile `entity-resolution.md` seed-map-priority + LLM confidence rows vs ADR-0005.
4. **`CLAUDE.md` split (D4) — DEFERRED** by owner. Not now; revisit before first public push.

New since: ADR-0011 (resolution architecture) — thresholds/handling provisional, to be tuned by stress-testing the resolver vs real source data.

---

## 2026-06-14 — SEC 13F-HR extraction: pre-compute + daily update path

**Direction (confirmed during recon spike).** 13F-HR data is bounded, structured, and quarterly-cadence — feasible to pre-compute full corpus into SQLite rather than live-fetch. Daily check catches amendments (13F-HR/A) and new filings during the ~2-week quarterly burst window.

**Scope:**
- V1 = latest quarter only, filtered to filers holding seed media tickers (~200-500 filers)
- Backfill (historical quarters) deferred to temporal-tracking phase
- Full-map async job ingests entire portfolio per filer; answer-card reads media subset

**Assumption to validate:** pre-compute is actually feasible at SEC rate limits (10 req/sec) for the filtered filer set. Plumbing script tests this.

**Maps to ADR-0019 two-mode traversal:** fast track reads pre-computed graph, full-map extends it. No live SEC fetches on user request path.
