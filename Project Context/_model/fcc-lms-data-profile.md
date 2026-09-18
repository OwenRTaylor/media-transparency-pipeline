# FCC LMS Ownership — Data Profile

Source: OPIF MCP spot-checks, 2026-05-17. 17 stations, 7 structural shapes. Live API used for shape-discovery only — bulk LMS dump remains canonical source per invariant #14.

## Stations sampled

| Cat | Station | Parent | Apps | LMS/CDBS | Names | FRNs | %Other | Xfer | Notes |
|---|---|---|---|---|---|---|---|---|---|
| pubco_oo | WNBC | NBCU/Comcast | 728 | 475/253 | 131 | 68 | 30% | — | deepest chain |
| pubco_oo | KCBS-TV | Paramount→Skydance | 180 | 127/53 | 42 | 21 | 14% | 42 | rebrand SPAC shells |
| pubco_oo | WABC-TV | Disney | 147 | 93/54 | 17 | 11 | 0% | 7 | stable |
| group_sub | WBFF | Sinclair | 139 | 89/50 | 28 | 11 | 6% | 18 | |
| group_sub | WGN-TV | Nexstar/Tribune | 199 | 113/86 | 45 | 37 | 0% | 3 | ESOP+bankruptcy era |
| group_sub | KCTV | Gray/Meredith | 68 | 42/26 | 11 | 14 | 0% | 7 | endowment trust |
| nonprofit | WETA-TV | GWETA | 24 | 12/12 | 7 | 1 | 0% | 0 | 323-E |
| nonprofit | WGBH-TV | WGBH Educ Found | 23 | 14/9 | 2 | 1 | 0% | 0 | 323-E |
| nonprofit | KQED | KQED Inc | 27 | 17/10 | 5 | 1 | 0% | 0 | 323-E, NCPB rename |
| pe_ctrl | KROQ-FM | Audacy/CBS legacy | 186 | 124/62 | 43 | 20 | 18% | 32 | Redstone trust |
| pe_ctrl | WBZ-FM | Beasley | 204 | 131/73 | 40 | 23 | 0% | 17 | estate trust |
| pe_ctrl | KFI | iHeart (Bain+THL) | 358 | 213/145 | 59 | 30 | 0% | 12 | PE GPs named |
| pe_ctrl | WHTZ | iHeart | 316 | 192/124 | 59 | 29 | 0% | 12 | ≈KFI |
| pe_emerged | WMAL-FM | Cumulus post-BK | 327 | 214/113 | 64 | 46 | 23% | — | shell LLC blockers |
| pe_emerged | WSB-TV | CMG/Apollo | 202 | 155/47 | 38 | 11 | 0% | **75** | Apollo VOTECO |
| pe_emerged | KIRO-TV | CMG/Apollo | 203 | 159/44 | 40 | 13 | 0% | **78** | ≈WSB |
| family | WCVB | Hearst | 170 | 102/68 | 21 | 12 | 19% | 0 | SEE EXHIBIT placeholder |
| family | KSL-TV | Bonneville/LDS | 61 | 41/20 | 7 | 8 | 0% | 0 | DMC stack |

## Cross-station invariants (held)

- `formNumber`: 323 commercial, 323-E nonprofit. CDBS legacy stores `formNumber=323` + `realFormNumber=323-E` — normalize cross-system.
- Source-system split: every station has LMS + CDBS rows. CDBS = pre-2013.
- `relationship` field: filled on LMS rows, **blank on all CDBS rows** universally. Pre-2013 derive from `appType`.
- `positionalIntOff/Dir/Lim/Gen/Llc/Own/Stk/Crd/Inv` typed cols ≈ 0% fill across ALL stations. Don't drop, but don't expect data.
- `positionalIntOther` filer-discretionary 0–30%. Some pubcos (iHeart) enumerate chain via rows; others narrate in Other free-text. Not a reliable chain indicator.
- `governance ≠ ownership` invariant survives: nonprofit filings use identical schema, zero board fields. Board comes from IRS 990.

## Schema-fragility hits (14)

1. **323 vs 323-E form variant.** Need `form_type` enum + cross-system normalization (CDBS `realFormNumber` overrides `formNumber`).
2. **Filing↔facility = M:N.** Combined filings cover multiple stations (WETA TV+FM rows reference `appFacilityId` ≠ `facilityId`). Junction table required.
3. **`SEE EXHIBIT 1` placeholder rows** (Hearst 14 rows). Structured row intentionally empty; data in attached exhibit doc. Flag `is_placeholder_row`.
4. **Transfer-of-control filings = state-change events**, distinct from biennials. `filing_type` enum needed: Biennial / Validation / Transfer / Amendment / Ownership-Other / Ownership-Sale. Transfer-density = Phase-2 entity-event signal.
5. **Sibling-sub flooding.** WUSA filings list Detroit Free Press, Detroit News (sibling Gannett subs, not WUSA-chain). Without typed positional flags, `partyName` ≠ "owns this station". Filing-topology parsing required, not flat row extraction.
6. **Variable disclosure depth.** Top-tier trust/UBO sometimes in filing (Audacy/Redstone trust, Bonneville/DMC), sometimes external-only (Hearst family). Need `disclosed_in_filing` bool per relationship.
7. **Numbered/named blocker LLCs**: `RADIO LICENSE HOLDING VII, LLC`, `WUSA-TV, INC.`, `*VOTECO, LLC`. Single-station shell licensees. Flag `is_shell_licensee` on entity; UI shows parent operating co.
8. **Sentinel-null variants**: `""`, `"NO FRN"`, `"N/A"`. Stage-time normalizer → SQL NULL.
9. **Duplicate rows in source.** Same `applicationId` appears 2-8 times in OPIF responses (WABC, KCTV, KQED, KSL). Stage-time dedupe `UNIQUE(applicationId, partyName, applicantFrn)`.
10. **FRN→entity is M:N.** Bonneville: 3 distinct FRNs each carry identical 4-name set (Bonneville Holding / Intl / DMC / DMC Trust). Entity_id independent of FRN; junction table maps FRN↔entity.
11. **Name-change-under-stable-FRN = corporate event.** Paramount FRN 0037387990: AOZORA → FURAITO → HARBOR LIGHTS → HIKOUKI → PARAMOUNT SKYDANCE (merger SPAC shells). ABC FRN 0030871354: 5 name variants over time. Emit `corporate_event` records w/ timestamps.
12. **Trust subtypes**: family voting trust (Cox), endowment trust (Meredith), life-income trust (Redstone), estate reduction trust (Beasley), corporate-vehicle trust (DMC/LDS), ESOP trustee (GreatBanc/Tribune). Taxonomy needs ESOP subtype + family-voting subtype.
13. **PE GP/LP funds named in filings.** `THOMAS H. LEE PARTNERS, L.P.`, `BAIN CAPITAL (CC) IX, L.P`, `AP IX TITAN HOLDINGS, L.P.`. `*VOTECO*` suffix = voting-control shell. `private_equity` relationship type data-supported.
14. **State-flag suffix in name**: `"WGN CONTINENTAL BROADCASTING COMPANY, DEBTOR-IN-POSSESSION"`. Bankruptcy state encoded in free-text partyName. Suffix-parse during extraction; emit as relationship `status`.

## Date-string formats

- `accurateDate`, `stampedDate`, `receivedDate`: `MM/DD/YYYY` strings. Parse to ISO at staging.
- `accurateDate` 76–77% fill (intent date). `stampedDate` 100% fill (FCC receipt). Use accurate, fallback stamped, for `last_verified`.

## Volume estimate

Row counts scale with parent-history density:
- Nonprofit single-entity: ~25 apps/station
- Group-sub: ~70–200
- Pubco/PE clean: ~150–360
- Pubco/PE chain-deep: ~700+ (NBCU)

Phase-1 anchors × parties × filings → **O(100k–500k ownership rows** projected for ~100 outlets. Index on `(entity_id, accurate_date)`, `(facility_id, accurate_date)`, `(filing_id)`, `(frn)`.

## Net invariant adjustments

- INV-#1 extension: entity_id ≠ name AND entity_id ≠ FRN.
- New INV: dedupe by `applicationId` at staging.
- New INV: name-change-under-stable-FRN = corporate event, not error.
- New INV: per-parent shape > per-category shape. Parser specialization at anchor-parent granularity.

## Meta — discovery insight

**Category is not the schema-shaping axis. Parent-entity history is.**
- Same parent → same FRNs reused, near-identical row patterns (KFI≈WHTZ; WSB≈KIRO).
- Different parents same category → wildly divergent (KCBS≠WABC; WGN≠KCTV).
- → Future discovery (SEC, IRS) should spot-check per anchor parent, not per abstract category.

## Per-entity verification implication

Each Phase-1 anchor (18) needs its own truth-set fixture. Cross-DB resolution (FCC↔SEC↔IRS) cannot rely on generic rules — must be validated entity-by-entity against a manually curated reference (the existing `seed_map.json` plan, but expanded). Manual seed map (INV-#8) carries more weight than initially scoped.
