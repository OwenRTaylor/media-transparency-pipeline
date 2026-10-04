# Handoff

Updated: 2026-09-19
Branch: main. **Nothing committed this session** — origin/main = 42b31d2. Owner authorizes commits per-action.

## Focus
First real vertical slice built + running on **real Fox data**: two Layer-1 extractors → Layer-3 staging → 8-table SQLite, plus the SEC↔FCC cross-source identity merge. Built across 3 parallel sessions (now ended); this session = contracts + SEC extractor + merge + review of the other two.

## What now works end-to-end (real data, anchor = Fox)
- Anchor pinned: **SEC "Fox Television Stations Inc" CIK 788511 ↔ FCC "Fox Television Stations LLC" FRN 0005795067.** (Modern Fox Corp CIK 1754301 absent from local submissions dump — snapshot predates 2019 reorg.)
- `contracts.py` — full 6-object in-memory contract + enums; gap-guard in `__post_init__`. Frozen interface all layers import.
- `extractors/sec/{extract,resolve}.py` — CIK → Entity + external_ids + attribute provenance + GAP records (SC 13D seen, no parser). `resolve()` = deterministic CIK else rapidfuzz.
- `extractors/fcc/{dat_reader,extract,resolve,name_core}.py` — FRN → licensee Entity + FRN/facility_id external_ids + provenance. `dat_reader` streams `|^|`-terminated multiline `.dat` (INV-15). `name_core` = ADR-0023 rename-vs-counterparty guard.
- `staging/{schema,stage,validate,export,keys,fixtures,run_staging}.py` — DuckDB stage → INV validation (ERROR blocks, SKIPPED surfaced) → idempotent 8-table SQLite. Dedupes source_documents, remaps provenance targets, persists merge tier. Output: `data/staging/media_transparency.sqlite` (gitignored).
- `resolution/{names,cross_source}.py` — cross-source merge (ADR-0025). Real Fox merges HIGH; negatives pass (Gannett rejected by distinctive-token guard; Fox Sports ≠ Fox TV by WRatio; never-silent guard fires).

## ADRs added this session
ADR-0023 (FCC rename-vs-counterparty) · ADR-0024 (address = positive-only tiebreaker) · ADR-0025 (merge = non-official "Likely" inference, never silent).

## Uncommitted (`git status --short`)
- M: `contracts.py`, `extractors/sec/{extract,resolve}.py`, `resolution/names.py`, `staging/{export,stage,validate}.py`, `extractors/fcc/__init__.py`, `_model/handoff.md`
- ??: `extractors/fcc/{dat_reader,extract,resolve,name_core}.py`, `resolution/cross_source.py`, `staging/{fixtures,keys,run_staging,schema}.py`
- `docs/adr.md` (ADR-0023..0025) — via Edit, shows as M.

## Active task — integration tile (tile 5)
Wire the real path end-to-end: `sec.extract` + `fcc.extract` → `cross_source` merge → staging → SQLite. Currently staging loads from `staging/fixtures.py` (synthetic Fox), not real extractor output. Merge lives in `resolution/`; Layer-3 orchestration home = empty `staging/dedupe.py:1`. Touches C's `staging/run_staging.py` — reconcile fixture path vs real path.

## Next concrete steps
1. Add validation: "every external_id with merge_confidence has a merge provenance record" (was P3, now buildable — `staging/validate.py`).
2. P2 (minor): `external_id`-targeted provenance remaps `target_id` to entity id, not the external_id row id — `staging/export.py`.
3. Then widen past Fox → tier calibration + empirical D3 floor (cutoffs in `cross_source.py` HIGH_CUTOFF/MEDIUM_CUTOFF are provisional placeholders).

## Deferred
`_model/TODO.md`. New: quarantined FCC counterparties (Tribune/Nexstar/KTVU under Fox FRN) are latent transfer/ownership edges — a real `relationship` source later. Dedup: `resolution/names.py` normalize/tokens duplicates `discovery/cross_source_overlap.py` — unify.

## Env notes
`python3` not `python`. No venv — system 3.12. Installed: `rapidfuzz`, `duckdb` (C added). Absent: `edgartools`, `pandas`, `lxml`. FCC/OPIF/contours MCP servers failed to connect this session.
