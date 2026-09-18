# Entity Discovery — Design Doc

## Why

Pipeline needs to know which entities ARE media companies before extractors can run at scale. Prior plan assumed curated seed list (~100 outlets, ~18 parents). Hybrid approach casts multiple discovery nets, merges via entity resolution, verifies with extractor output.

## Discovery Sources

### A. SEC SIC filter (available now)
Bulk `submissions/` data (272K files, local). Each has `sic`, `sicDescription`, `name`, `cik`, `tickers`, `ein`, `entityType`, `website`, `category`.

Core media SIC codes:
- 2711 Newspapers
- 2721 Periodicals
- 2731 Books
- 2741 Miscellaneous Publishing
- 4832 Radio Broadcasting
- 4833 Television Broadcasting
- 4841 Cable & Pay TV
- 7812 Motion Picture Production
- 7819 Allied to Motion Picture Production
- 7822 Motion Picture Distribution
- 7829 Allied to Motion Picture Distribution
- 7830 Motion Picture Theaters

Scan result: ~1,286 entities from core SICs. Hits most known anchors (Fox, Disney, Comcast, NYT, Nexstar, Sinclair, Scripps, Salem, Cumulus, Audacy, iHeart, Paramount/Skydance). Known gaps: merged/delisted entities (Gannett), tech-classified streaming, private companies, subsidiaries under parent SIC.

Borderline SICs (noisy, evaluate case-by-case):
- 4812/4813 Telephone/Radiotelephone — telcos, not media (some overlap: AT&T owns Warner)
- 7372 Prepackaged Software — streaming platforms sometimes classified here
- 4899 Communications NEC — catch-all, some media
- 3663 Radio & TV Equipment — manufacturers, not media companies

### B. FCC LMS dump (available now)
`unfiltered_data/Current_LMS_Dump/` — all broadcast licensees. Media entities by definition. Provides FRN, call sign, facility ID, licensee name. No CIK/ticker/EIN.

### C. 13F reverse scan (requires extractor)
Scan known institutional holders' 13F portfolios → filter holdings where issuer has media SIC code. Discovers "which media companies do big funds hold" without pre-knowing the companies. Requires: (a) 13F extractor working, (b) CUSIP→CIK→SIC resolution chain.

### D. IRS 990 NTEE filter (available, untested)
`unfiltered_data/2026_TEOS_XML_*` — nonprofit 990 filings. NTEE codes A60-A69 cover media/communications nonprofits. Provides EIN, org name. No CIK/FRN.

### E. Curated seed entities (anchor test fixtures)
~18 anchor parents with known-good identifiers. Role = ground truth for validating automated discovery quality. Not the primary discovery input.

## Entity Resolution (Layer 2 concern, but discovery shapes it)

Same company appears differently across sources:
- SEC: "Fox Corporation" (CIK 0001754301)
- FCC: "Fox Television Stations, LLC" (FRN)
- 13F: "FOX CORP" (CUSIP issuer name)

Resolution strategies (to prototype):
- CIK↔FRN bridging via company name fuzzy match (`rapidfuzz`)
- EIN present in both SEC submissions and IRS 990
- Ticker overlap between SEC and 13F
- Parent-subsidiary grouping (multiple CIKs, FRNs per parent)

Output: candidate entity table — each row = one source record, linked to a canonical entity via resolution. Source records preserved individually (provenance). Confidence score on each cross-source link.

## Known Gaps (hybrid still won't catch)

1. **Private companies with no SEC/FCC/IRS presence** — rare for media at scale, but exists (some PE-owned digital media)
2. **Companies misclassified by SIC** — SEC SIC assignment is self-reported and sometimes wrong/outdated
3. **International parent companies** — out of Phase 1 scope (INV-18) but some US subsidiaries may appear
4. **Newly formed entities** — bulk data has a lag; live API could catch but violates INV-14

## Dependency Graph

```
Discovery track → entity resolution → candidate entity table
                                            ↓
Extractor tracks (13F, DEF 14A, FCC, etc.) — unit test on hardcoded IDs,
    integration test needs candidate table
                                            ↓
Verification/enrichment — extractor results feed back, fill gaps
```

## Open Questions

- How many FCC LMS entities overlap with SEC SIC-filtered entities? (testable now)
- What's the false-positive rate on SIC filtering? How many of the ~1,286 are actually media companies vs noise?
- Is there a simpler bridge between CIK and FRN than fuzzy name matching? (e.g., does FCC filing reference SEC CIK anywhere?)
- Output shape for candidate entity table — flat CSV for prototyping, or DuckDB staging table?

## Trust Tiers & Faceted Filtering (design, 2026-09-17)

**Core stance.** Output is not a single source of truth. Each extractor/match = a separate, self-labeled datum. The *server-side user* decides how much uncertainty to view; pipeline never drops, never adjudicates — it emits everything, correctly labeled, and hands off (INV-13: toggle logic lives in Node server, not pipeline). Aligns with INV-20 (murkiness visible), INV-38 (capture-or-lose).

**Tier model (two *kinds*, not one scale):**
- **Official** — categorical. Pulled directly from source, no probabilistic judgment by code. Can be wrong/stale (source's fault) but never *mis-judged by our code*. NOT the top of the probability scale.
- **Likely** — our probabilistic inference, graded **high / medium / low**.

Keep Official and Likely as different epistemic objects. A deterministic exact-key match and a 99% fuzzy match both read "strong" but are not the same thing — one can't be misjudged by code.

**Faceted filtering = union of tags.** Two facet families on every datum:
- **Source** — FCC / SEC / IRS (extensible)
- **Tier** — Official / High / Med / Low (per *atomic hop* — see chain note below)

User selects any combination; results = **union** (a datum shows if it matches a selected tag). Default view = Official only. Each datum always carries which source + tier it came from. Uncertain matches are *surfaced labeled*, not dropped — the human is the escalation path for algorithm-hard matches (cheaper + more honest than an LLM auto-promoter).

**Trust is a chain, not a tier (load-bearing).** A *derived* fact's trustworthiness = the chain of hops that establish it, e.g. fact A (low) —medium link→ fact B (high) —official link→ fact C (official). There is NO single "tier of A" — viewing A honestly means exposing *every hop's* tier, including the cross-source identity-merge hop. **Pipeline exposes the entire chain, every hop labeled; server decides how to collapse it legibly (INV-13). Pipeline captures all, decides nothing** (INV-38).

**Floor (of Low) — deferred, empirical (INV: concrete-first).** Set once the pipeline runs against real data. It's an *operating point on the precision/recall curve*: the recall you stop caring about because precision there ≈ chance. Testable move: plot score distribution, hand-label a sample straddling candidate cutoffs, find the precision cliff.
- **Two floors, possibly different values:** (a) *generation/blocking floor* — don't even form pairs below it (upstream, saves compute); (b) *display floor* — form+store, hide below a line (downstream, kills rabbit-holes). A frontend-only floor saves zero compute.

### Schema viability vs data-model.md — verdict: viable, no schema change required

Reconsidered 2026-09-17 (owner corrected two earlier over-flags — kept here as the settled view).

1. **[RESOLVED — no separate field needed] Official as a tier value is fine.** For an *atomic hop* (one fact, one source, one extraction, one link), a single tier `{official, high, medium, low}` fully captures it. Requirements are consumer-side discipline, not schema: (a) server treats `official` as **categorical**, never sorted as "highest probability"; (b) calibration/probability math **excludes** `official` (a deterministic match has no score to calibrate). `official` must mean *deterministic at this hop* — source AND extraction AND cross-source link all deterministic (or no link needed) — to stay atomic and honest. Earlier "add a `link_method` column" was overengineering; dropped.

2. **[RESOLVED — malformed question] No single "edge tier" for a derived fact.** Trust is a **chain**, not a tier (see chain note above). Asking "best-provenance vs all" was wrong — the answer is *neither*: expose every hop's tier, let the server collapse for display. Nothing to decide in-pipeline.

3. **[THE REAL REQUIREMENT — discipline, not schema] Every hop must write its own tier, including the identity-merge.** A cross-source match ("FCC-Y IS SEC-X") is an identity assertion, stored as one entity carrying both external IDs (`entity_external_ids`, ADR-0013). Provenance on `external_id` (`target_type='external_id'`) *can* carry the merge's confidence+method — the schema already allows it. Load-bearing rule: **the resolver must write the merge's tier into that provenance and never merge silently.** Otherwise a fuzzy merge becomes an invisible weak link and chain-tracing lies. This is a coding discipline for the resolver, enforced by validation — not a new table.

4. **[OK] `confidence` enum stays high/med/low.** `official` is a tier *value* the server reads categorically; no enum migration, no new column. Union-of-tags filtering is supported at provenance grain: every fact → provenance → source (via source_document) + confidence + extraction_method; the chain is reconstructed by graph traversal. **The provenance subsystem (ADR-0013) already solves this — it would have been required regardless of tiers.**

**Net:** no schema change. Two consumer-side disciplines (server reads `official` as categorical; resolver never merges silently). ADR only needed once the **floor** is empirically set — and possibly a small validation rule ("every cross-source merge has provenance with tier"). Until then this section is the working spec.

## Track

→ `_model/tracks/planned/entity-discovery.md`
