# Handoff

Updated: 2026-07-11
Branch: main

## Focus
Entity discovery D3 — improving cross-source overlap accuracy. Iterating on matching quality.

## In progress
D3 cross-source overlap: `pipeline/discovery/cross_source_overlap.py`
- v1 complete. Fuzzy name match (rapidfuzz WRatio) SEC↔FCC with name normalization, blocking, distinctive-token overlap guard.
- Current results: 369 high / 9,344 medium / 1,504 low matches. ~2% false positive rate in high tier.
- Dedupe: SEC 1,267→1,257 unique. FCC 135,640→122,595 unique.
- 16/18 anchor entities found at high confidence.
- Output: `data/discovery/cross_source_matches.json`, `cross_source_summary.json`

**Next steps — accuracy improvement (owner wants to iterate until high confidence):**
1. ~~EIN deterministic bridge~~ — DEAD END (checked 2026-09-17). FCC keys all parties by FRN (`interest_holder_frn`, `apar_frn`), never EIN/TIN. SEC uses CIK/EIN. Namespaces disjoint — no shared deterministic key in bulk data. Fuzzy/address/LLM are the only bridges.
2. Address matching (SEC state/addr + FCC licensee addr) to promote medium→high
3. LLM judge (Haiku) on medium+high pairs — ~$0.07 for 9,700 pairs. Not INV-10 violation (resolution decision, not source extraction)
4. Repeat until high-tier false positive rate ≈ 0

## Active tracks
1. **Entity discovery** (`_model/tracks/planned/entity-discovery.md`) — D3 in progress, iterating.
   - D1: SEC SIC scan → 1,267 candidates. `pipeline/discovery/sec_sic_scan.py`
   - D2: FCC LMS scan → 135,640 candidates. `pipeline/discovery/fcc_lms_scan.py`
   - D3: cross-source overlap → `pipeline/discovery/cross_source_overlap.py`
2. **13F extractor** (`_model/tracks/planned/13f-extractor.md`) — paused.

## Recent commits
011b813 docs: add ADR-0014 through ADR-0017, update SEC recon script
a2970f7 docs: add ADR log through ADR-0013 evidence/provenance subsystem
f8ee027 Initial commit

## Uncommitted
| File | Change |
|---|---|
| `.gitignore` | M |
| `docs/adr.md` | M — ADR-0018 through ADR-0022 |
| `pipeline/discovery/` | NEW — sec_sic_scan.py, fcc_lms_scan.py, cross_source_overlap.py, __init__.py |
| `data/discovery/` | NEW — sec/fcc candidates + cross_source_matches.json + cross_source_summary.json |
| `_model/design/entity-discovery.md` | NEW |
| `_model/tracks/planned/entity-discovery.md` | NEW |
| `_model/tracks/planned/13f-extractor.md` | NEW |
| `_model/design/13f-extractor.md` | NEW |
| `notebooks/*.py` | NEW — recon scripts |
| `pipeline/` | NEW — scaffold + discovery |
| `config/` | NEW — company_tickers.json, domain_map.json |
| `Makefile` | NEW |

## Deferred
- `_model/TODO.md` — CUSIP→entity resolution, SALM plain-text tables, D1b llm-use policy, FCC LMS threads, 13D/8-K, 10-K Exhibit 21
