# INDEX — Router

Router only. No content. Points to docs and when to read them.

## Always-Loaded (via /project-context)
| File | Purpose |
|------|---------|
| `_model/handoff.md` | Session pickup state |
| `_model/INDEX.md` | This file — router |
| `_model/invariants.md` | Project-wide constraints. Apply immediately. |
## Load-on-Demand

### Design docs (`_model/design/`)
| File | When to read |
|------|--------------|
| `_model/design/entity-discovery.md` | Building or modifying entity discovery pipeline |
| `_model/design/13f-extractor.md` | Building or modifying 13F-HR extraction module |

### Tracks (`_model/tracks/`)
| File | When to read |
|------|--------------|
| `_model/tracks/planned/entity-discovery.md` | Working on entity discovery pipeline |
| `_model/tracks/planned/13f-extractor.md` | Working on 13F extractor build steps |

### Domain knowledge
| File | When to read |
|------|--------------|
| `_model/snapshot.md` | Repo state, downloaded data status, code inventory |
| `_model/scope.md` | Phase 1 boundary check, "is this in scope?" |
| `_model/data-sources.md` | Working w/ FCC LMS / SEC / IRS bulk data, source URLs, schemas, rate limits |
| `_model/entity-resolution.md` | Cross-DB matching, fuzzy joins, person dedup, relationship typing, confidence rules |
| `_model/data-model.md` | Schema design, architecture (Layer 1/2/3), taxonomy, validation, output SQLite layout |
| `_model/fcc-lms-data-profile.md` | Empirical profile of FCC LMS/CDBS ownership data (17-station spot-check, 14 fragility hits, volume est.) |
| `_model/discovery-method.md` | Discovery-phase reflections — MCP-probe method, per-anchor verification mandate, transferable to SEC/IRS stages |
| `_model/bulk-lms-discovery-reflection.md` | Session 2026-05-17 pickup aid — bulk LMS spot-check deltas vs OPIF profile, 9 new fragility hits, 9 open threads. Read when resuming FCC bulk discovery. |
| `_model/seed-anchors.md` | Starter outlets for v1, category list + selection rule |
| `_model/philosophy.md` | Design heuristic / trade-off question |
| `_model/maintenance.md` | Deciding what doc to update after a change |
| `_model/TODO.md` | Deferred design work. Read when picking up a parked problem or before starting new design thread (check overlap). |
| `_human/anytype.md` | (local only) Owner asks to read/write Anytype notes. Lists space/project/type IDs, custom props, interaction rules |
| `_model/flows.md` | (not yet written) Call graph, mutable fields, lifecycles |
| `_model/features/<stage>.md` | (not yet written) Per pipeline-stage when implemented |

### External (canonical source — never modify)
| File | When to read |
|------|--------------|
| `docs/adr.md` | Append-only ADR log (git-tracked). Read when checking why a design choice was made, or to record a new decision/reversal. |
| `external/news-transparency-pdd.md` | Product PDD — answer card design, user-facing |
| `external/news-transparency-data-pipeline-pdd.md` | Authoritative pipeline PDD — full detail when fragment insufficient |
| `external/news-transparency-extended-vision.md` | Phase 2+ concepts (multi-hop, temporal, regulatory, events, intl) |
| `external/data-download-checklist.md` | Download URLs + exhaustive source detail |
| `external/future-data-sources.md` | Tier 1-3 future sources (Form D, Wikidata, RollUp, PitchBook, etc.) |
| `external/learning_context_summary.txt` | (local only) Owner profile + working-style context |
