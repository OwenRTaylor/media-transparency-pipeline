# Discovery Method — Reflections

Captured 2026-05-17 after FCC LMS spot-check phase (17 stations, MCP-driven). Transferable to upcoming SEC EDGAR + IRS 990 discovery.

## Method that worked

- **MCP live API for shape-discovery only.** Bulk dump remains canonical (INV-#14). Live = cheap probe, not pipeline source.
- **Spot-check pattern**: 1 anchor per parent, profile via DuckDB/Python script, save large payloads to disk, ingest summaries only into context.
- **Profile per file**: app count, source-system split, fill rate per column, distinct counts, top partyName, FRN→name-set mapping, transfer-density.
- **Cross-station table** to expose intra-category variance.
- **Look for sentinels**: literal `"NO FRN"`, `"SEE EXHIBIT 1"`, `"DEBTOR-IN-POSSESSION"`, duplicate `applicationId`.

## Axis correction

**Category is not the shape-axis. Parent-entity history is.**

| Observation | Evidence |
|---|---|
| Same parent → near-identical shape | KFI≈WHTZ (both iHeart); WSB≈KIRO (both Apollo/CMG) |
| Different parents same category → divergent | KCBS≠WABC (pubco_oo); WGN≠KCTV (group_sub) |

→ Sample per anchor parent, not per abstract category bucket. Diminishing returns past ~2 per parent.

## Transferable to SEC / IRS stages

| Stage | Discovery probe | What to look for |
|---|---|---|
| SEC EDGAR | `sec-edgar-mcp` one proxy + one 13F per public anchor | section-naming variance, table-malformation rate, beneficial-owner threshold disclosure patterns |
| IRS 990 | `propublica-mcp` one 990 per nonprofit anchor + Schedule O | board listing format variance, related-org disclosure, in-kind vs cash, fiscal-year offsets |
| Form ADV (PE) | n/a MCP — bulk file probe | chain-of-control disclosure depth, GP/LP/voteco shell patterns |

Same script-driven profile, same per-parent sampling, same sentinel-hunt.

## Volume budgeting

- 17 OPIF ownership pulls + ~12 saved-to-disk payloads = ~1.5MB on-disk, kept out of context. Cheap.
- Profile-time: 1 Python pass per batch of ~10 files.
- Diminishing-returns cliff: after seeing 2 same-parent stations match closely, additional samples within same parent are non-informative.

## Per-entity verification requirement (new — was understated)

Discovery exposed:

1. **FRN→entity is M:N** (Bonneville 3 FRNs ↔ 1 entity stack).
2. **Name explosion under stable FRN** (Paramount: 5 SPAC shells; ABC: 5 historical names) — pure fuzzy-match will mis-merge or fail-to-merge.
3. **Variable disclosure depth** — UBO sometimes in filing (Audacy→Redstone, Bonneville→DMC) sometimes external-only (Hearst family trust).
4. **Sibling-sub flooding** — WUSA filings list non-WUSA Gannett subs (Detroit papers). PartyName-walk extracts wrong relationships without disambiguation.

→ Each of 18 Phase-1 anchors needs hand-curated truth fixture. `seed_map.json` (INV-#8) is **per-anchor verification ledger**, not optional convenience.

Recommended structure: `_human/anchors/<entity-slug>.md` per anchor. Fields:
- Known FRNs (with date-range each valid)
- Known name variants (historical + current)
- Known parent chain (with `disclosed_in_filing` vs `external_source` flag)
- Trail-end boundary (where honesty kicks in: "no further public records")
- Source citations
- Date last refreshed

Pipeline validates extraction against fixtures. Fixtures are authority, not heuristic.

## Open questions surfaced — defer to relevant stage

- CDBS legacy (pre-2013) `relationship` field universally blank — backfill from `appType` or flag pre-2013 as untyped?
- `positionalIntOther` free-text — LLM extraction (INV-#10 second-pass) when populated, or skip?
- "DEBTOR-IN-POSSESSION" / "VOTECO" / `TRUST` suffix patterns — pre-extract via regex before fuzzy-match, or post-merge cleanup?
- Same applicationId duplicate-row pattern in OPIF API — does bulk LMS dump also dupe, or is it API-response artifact? Verify when bulk profiled.

## Negative findings (don't redo)

- `opif_frn_relationships` returns facility list only, NOT parent-corp tree. Not useful for chain discovery.
- `opif_global_search` substring-matches party/city names (WETA matched "COWETA" county). Verify exact match before trusting result count.
- `opif_facility_detail` thin — call sign, party, contacts only. Won't replace `opif_ownership_by_facility`.

## When to re-run

Re-discover only if:
- Adding a 19th anchor with structurally novel parent (e.g. SPAC-acquired, foreign-owned).
- Bulk LMS dump shape differs materially from API (verify during stage-2 ingestion).
- New form variant appears (323-S, post-2025 FCC rule changes).
