# Entity Resolution

Hardest problem in pipeline. Three DBs, no shared keys, inconsistent names.

## Example
- FCC: `NEXSTAR MEDIA INC.` (subsidiary licensee)
- SEC: `Nexstar Media Group, Inc.` (parent filing proxy)
- IRS: `Nexstar Foundation` (if exists)

Same family. Different names. **10-K Exhibit 21 = bridge** (lists subsidiaries under parent).

## Resolution architecture (locked 2026-05-20, ADR-0011)

Two distinct resolutions — never conflated:

**Resolution #1 — URL → entity.** Source-agnostic. URL-normalize → `domain_map` lookup → entity. Own pre-traversal module; Layer 2 always receives an entity, never a URL. Deterministic — no ambiguity, no pick-list.

**Resolution #2 — entity → source key** (CIK/FRN/EIN). Per-source, lives in each extractor as `resolve()`.

Extractor interface (refines ADR-0007):
- `resolve(entity) → ResolutionResult{ source_key|None, confidence, candidates[], provenance, method }`
- `extract(source_key) → ExtractorResult` (entities, relationships, provenance, coverage_log)

**SDK-confinement:** no source SDK (`edgartools`, …) imported outside its extractor. SDK = fetch backend, not resolution definition.

**Shared vs per-extractor:** shared = URL normalize, `domain_map`, name normalize + `rapidfuzz` scoring, confidence rules, interface, DB-cache lookup. Per-extractor = the source-search call + record→canonical mapping.

**Five-tier outcome** — `resolve()` result drives handling:
| Outcome | Handling |
|---|---|
| 1 match, high confidence | auto-accept |
| small set, no winner (≤ ~20) | human pick-list (post-v1 UX) |
| large set (> ~20) | resolution failure — filter broken |
| 0 matches | trail-end honest (INV-19) |
| 1 match, low confidence | flag — never silent auto-accept |

v1 = unique-confident → accept, else flag/trail-end (no human ask). `candidates[]` exists day one so pick-list bolts on with no refactor. Thresholds + per-source matching strategy **provisional — tune by stress-testing vs real source data.**

## Resolution priority

> ⚠ Stale vs ADR-0005: `seed_map.json` below is listed as resolution priority #1 — it is now fixture-only, not a resolution input. LLM confidence rows are v2-only. Reconcile in the D3 `_model/*` audit.

### 1. Manual seed map (highest confidence)
`seed_map.json`. Hand-built for top 25-30 entities. Encodes knowledge no algorithm derives: VIE consolidation, shared-services agreements, duopolies.

Example entry:
```json
"nexstar": {
  "sec_cik": "1142417",
  "sec_name": "Nexstar Media Group, Inc.",
  "fcc_licensee_names": ["NEXSTAR MEDIA INC.", "MISSION BROADCASTING INC."],
  "fcc_frns": ["0004476335", "0003769540"],
  "domains": ["nexstardigital.com"],
  "notes": "Mission Broadcasting is VIE consolidated by Nexstar"
}
```

### 2. Exhibit 21 → FCC licensee fuzzy match (medium-high)
For each media CIK: parse 10-K Ex 21 → subsidiary names. Normalize (uppercase, strip LLC/INC/CORP, collapse whitespace). Join to FCC licensees via rapidfuzz `token_sort_ratio ≥ 90`.

```sql
SELECT sec.parent_cik, sec.subsidiary_name, fcc.licensee_name, fcc.frn
FROM sec_subsidiaries sec
JOIN fcc_licensees fcc
  ON rapidfuzz_ratio(normalize(sec.subsidiary_name), normalize(fcc.licensee_name)) >= 90
WHERE sec.parent_cik IN (SELECT cik FROM media_companies)
```

Review all <95 manually. ~few hundred matches total.

### 3. FRN expansion (highest leverage)
One licensee matched → FRN groups all co-licensed stations. FRN = FCC's stable legal-entity ID. Single match propagates to dozens/hundreds of stations.

### 4. Name similarity fallback (low confidence)
For unresolved: direct fuzzy on SEC company name vs FCC licensee. Score 75-84 = `low`, flag for review. More false positives — manual review required.

## What doesn't resolve (and that's OK)
- Small independent stations: local LLC, no SEC, no nonprofit → legitimate trail-end
- Private companies w/o SEC reporting (Alden, before public M&A) → seed map handles
- Pure nonprofits: no FCC, no SEC → IRS-only, standalone

## Person dedup
Same person across:
- SEC DEF 14A beneficial owner
- FCC Form 323 attributable interest
- IRS 990 Part VII officer/director

**Strategy:** normalize names (lowercase, strip Jr./III). Match on name + role + org. FRN helps for FCC-only. SEC↔IRS has no shared person ID → name match primary. Flag ambiguous for manual review.

## Relationship type assignment
| Source signal | Type |
|---|---|
| SEC DEF 14A >50% voting class | `family_control` or `direct_ownership` |
| SEC DEF 14A dual-class supervoting | `family_control` + qualifier |
| SEC DEF 14A controlling trust | `trust_structure` |
| SEC SC 13G 5%+ passive | `major_shareholder` |
| SEC SC 13D 5%+ active | `direct_ownership` or `private_equity` |
| SEC 10-K Ex 21 subsidiary | `parent_company` |
| FCC Form 323 licensee | `parent_company` (station → licensee) |
| FCC Form 323 >50% attributable | `direct_ownership` |
| FCC Form 323 officer/director | relationship on person, not separate type |
| IRS 990 Part VII | `governance` / `board_control` (nonprofit — NOT ownership) |
| IRS 990 Schedule R | `parent_company` or `nonprofit_funding` per field |

**Note:** taxonomy must include `governance` for nonprofits. Nobody "owns" NPR.

## Confidence
| Method | Confidence |
|---|---|
| Manual seed match | high |
| Exact normalized name match | high |
| Fuzzy ≥95 | high |
| Fuzzy 85-94 | medium |
| Fuzzy 75-84 | low (flag) |
| LLM-extracted, validated | medium |
| LLM-extracted, unvalidated | low |

## Validation (post-extraction)
- % cols sum ~100% per share class (allow rounding, treasury)
- Share counts consistent w/ total outstanding
- Shareholder names parseable (not HTML garble)
- ≥1 record per filing (zero = parser failure, not real result)

Fail → flagged for manual review.

## SEC HTML extraction (where most pipeline complexity lives)
**First pass — automated:**
1. Load filing HTML (BS4 / lxml)
2. Find `<table>` elements
3. Score each: column headers / surrounding text contain "beneficial ownership", "percent of class", "shares beneficially owned", "title of class"
4. Extract highest-scoring table
5. Map columns → schema (shareholder name, class, shares, %, footnotes)

**Second pass — LLM fallback** (Claude Sonnet, ~$0.01-0.05/filing, ~$1-5 total for 100):
- Triggered: no table found, structure unrecognized, validation fail
- Prompt extracts as JSON: shareholder_name, share_class, shares_held, percent_of_class, is_controlling, control_mechanism, notes
- Include trust + natural-person controller if disclosed

10-K Ex 21: table OR text list. SC 13G: standardized, 90%+ format-aware extractor success.
