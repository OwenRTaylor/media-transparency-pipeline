# 13F-HR Extractor — Track

**Status:** scoping
**Scope:** Build Layer 1 13F-HR extraction module. Transforms edgartools ThirteenF output into contract types (entities, relationships, provenance). Handles combination reports, rate limiting, document cache.
**Design doc:** `_model/design/13f-extractor.md`

## Checklist

- [ ] T1: Contracts — define all shared dataclasses in `pipeline/contracts.py`
- [ ] T2: 13F extraction core — `pipeline/extractors/sec/thirteenf.py`, single-filer `extract_13f(cik) → ExtractorResult`
- [ ] T3: Rate limiter — throttle wrapper for SEC requests
- [ ] T4: Document cache — raw XML to disk, Tier C access links
- [ ] T5: Batch extraction — iterate filer CIK list, collect results
- [ ] T6: SEC extract dispatcher — `extract.py` routes by filing type
- [ ] T7: Filer list — populate `config/known_13f_filers.json` with ~15-25 known major institutional holders (ADR-0021)
- [ ] T8: Wire public interface — `extractors/sec/__init__.py` exports `resolve()` + `extract()`

## Test impact
- New test files needed for contracts, thirteenf, batch extraction
- Integration test: run against Vanguard CIK, verify output shapes

## Uncommitted changes
(none yet — track just created)

## Notes
- CUSIP→entity resolution deferred to Layer 2 (extractor emits stubs)
- Combination report aggregation by (Cusip, filer_CIK), sub-manager detail in detail_payload
- Filer discovery resolved: curated shortlist (ADR-0021)
