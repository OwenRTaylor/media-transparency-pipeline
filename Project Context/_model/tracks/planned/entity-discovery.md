# Entity Discovery — Track

**Status:** spiking
**Scope:** Build discovery pipeline that identifies media entities across regulatory data sources, resolves cross-source matches, produces candidate entity table for extractor integration testing.
**Design doc:** `_model/design/entity-discovery.md`
**ADR:** ADR-0022

## Checklist

- [x] D1: SEC SIC scan — `pipeline/discovery/sec_sic_scan.py`. 1,267 candidates from 272K submissions. Output: `data/discovery/sec_media_candidates.json`. Hits: Fox(9), Comcast(6), Warner(7), Salem(15), most anchors. Miss: AMC Networks (blank SIC), Gannett (merged). 38 with tickers, 1,183 with EIN.
- [x] D2: FCC LMS scan — `pipeline/discovery/fcc_lms_scan.py`. Two-pass: application_facility.dat (5,979 licensees) + app_party.dat (129K additional). Output: `data/discovery/fcc_media_candidates.json`. 135,640 total — includes full spectrum from Nexstar (5,030 fac) to individual station owners (1-3 fac). Per INV-24 ("it's just people"), individual licensees = valid trail-end entities, not noise. All anchors found incl. radio cos (Salem, Cumulus, iHeart/iHM, Audacy, Beasley, Entercom, Townsquare). Disney as "THE WALT DISNEY COMPANY". Known junk: literal "Individual" placeholder entry (6,204 refs). Addresses pasted into name fields need cleanup.
- [ ] D3: Cross-source overlap — compare SEC and FCC candidate lists, measure overlap by name fuzzy match, identify bridge fields
- [ ] D4: Entity resolution prototype — merge SEC + FCC candidates into unified entity table with source-record links and confidence scores
- [ ] D5: Validate against seed anchors — check ~18 known parents against discovery output, measure recall and precision
- [ ] D6: 13F reverse scan (requires 13F extractor) — scan institutional holders, filter holdings by media SIC, discover additional media entities
- [ ] D7: IRS 990 NTEE scan — filter nonprofit 990s for media NTEE codes, add to candidate table
- [ ] D8: Gap analysis — document what discovery misses and why (private cos, misclassified SICs, merged entities)

## Dependencies

- D1, D2: independent, can run in parallel
- D3: needs D1 + D2
- D4: needs D3
- D5: needs D4 + seed anchors defined
- D6: needs 13F extractor track T2 (single-filer extraction working)
- D7: independent, can run anytime
- D8: needs D4-D7

## Notes

- D1-D5 = core discovery. D6-D7 = coverage expansion. D8 = quality check.
- Contracts kept simple during prototyping — output shape emerges from what we find.
- This track feeds INTO extractor tracks — extractors can unit-test independently but need discovery output for integration testing.
