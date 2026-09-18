# 13F-HR Extractor — Design Doc

## Why

13F-HR filings answer "who holds significant positions in this public company?" — the institutional-holder DOWN leg of the ownership graph (ADR-0019). Complements DEF 14A (who owns this company's voting shares) and 10-K Exhibit 21 (what subsidiaries does this parent own). Every SEC-registered investment manager with ≥$100M AUM files quarterly. ~6,000 filers total, ~200-500 hold media securities.

Pipeline pre-computes 13F data into SQLite (ADR-0020). Answer-card fast track reads pre-computed data, never hits SEC live (INV-14). Daily sync catches new filings + amendments during quarterly burst windows.

## What Exists

### Recon findings (ADR-0020, `notebooks/sec_13f_plumbing.py`)
- `edgartools.ThirteenF` = first-class. `.infotable` DataFrame: 13 cols (Issuer, Class, Cusip, Value, SharesPrnAmount, InvestmentDiscretion, OtherManager, SoleVoting, SharedVoting, NonVoting, Ticker, Type, PutCall)
- `.infotable_xml` = raw XML for provenance anchoring
- Vanguard: 17,686 holdings, 3.7s. BlackRock: 50,651 holdings, combination report w/ 30 sub-managers
- Combination reports: multiple rows per CUSIP per filer (one per sub-manager). Need aggregation by `(Cusip, filer_CIK)`
- `other_managers` attribute on combination reports: list of sub-manager objects w/ `name`, `cik`, `file_number`, `sequence_number`
- Reverse lookup works: iterate known holders → filter by ticker/CUSIP
- Timing: 200 filers ~12min, 500 ~31min, 6k ~6hr

### Scaffold state
- `pipeline/extractors/sec/` exists: `__init__.py` (docstring only), `extract.py` (docstring only), `resolve.py` (docstring only), `reference/` dir
- `pipeline/contracts.py`: `Entity` dataclass started (id, type, attributes). Other contracts not yet defined
- `config/company_tickers.json` exists (SEC's CIK→ticker map, useful for CUSIP resolution)

### Resolved design questions
- **Filer discovery (ADR-0021):** V1 uses curated known-holders shortlist in `config/known_13f_filers.json`, not brute-force AUM scan or EFTS search. ~15-25 known major institutional filers. Expansion manual + iterative.

### Open design question from handoff
CUSIP→entity resolution. edgartools resolves CUSIP→ticker. Ticker→entity needs either `domain_map` extension or new `security_map`. This is a Layer 2 concern but 13F extractor output shape must support it.

## How

### Module placement
```
pipeline/extractors/sec/
  __init__.py          # public interface: resolve(), extract()
  resolve.py           # entity → CIK (Resolution #2, shared across SEC filing types)
  extract.py           # dispatch: detect filing type → sub-extractor
  thirteenf.py         # NEW — 13F-specific extraction logic
  proxy.py             # FUTURE — DEF 14A extraction (from recon batch parser)
  reference/           # reference data (already exists)
```

`thirteenf.py` = the new file. `extract.py` becomes a dispatcher that routes to `thirteenf.py` or future `proxy.py` based on filing type. SDK-confinement (INV-30): `edgartools` imported only inside this package.

### Data flow

```
Input: CIK (filer) + filing type "13F-HR"
  ↓
edgartools: Company(cik).get_filings(form="13F-HR").latest()
  ↓
ThirteenF.infotable → DataFrame (all holdings)
ThirteenF.infotable_xml → raw XML (provenance anchor)
ThirteenF.other_managers → sub-manager list (combination reports)
  ↓
Transform to contract types:
  - Entity per filer (Fund/InvestmentGroup)
  - Entity per sub-manager if combination report
  - Entity per held security (stub — CUSIP + ticker + issuer name)
  - Relationship per holding: filer → security (type=major_shareholder)
  - Aggregate combination-report rows by (Cusip, filer_CIK)
  - detail_payload on relationship: {value, shares, voting breakdown, discretion, sub_manager_detail[]}
  - ProvenanceRecord per relationship: anchor_type=sec_13f_holding, anchor_payload={accession_no, cusip, row_index}
  - CoverageLog: what was queried, found, timing
  ↓
Output: ExtractorResult(entities, relationships, provenance, coverage_log)
```

### Contract compliance

Must return `ExtractorResult` per `data-model.md`:
- **Entities**: filer entity (type=Fund/InvestmentGroup), held-security stub entities (type=Company, minimal — CUSIP+ticker+issuer as attributes). Sub-manager entities from combination reports.
- **Relationships**: one per aggregated holding position. Type=`major_shareholder`. Direction: filer → held company. Confidence=high (13F is structured, mandatory filing).
  - `detail_type`: `sec_13f_holding`
  - `detail_payload`: `{value_usd, shares, share_type, sole_voting, shared_voting, no_voting, investment_discretion, report_period, sub_managers: [{name, cik, shares, discretion}...]}`
  - `detail_schema_version`: 1
  - `last_verified`: filing date (INV-6)
  - `status`: active
- **Provenance**: one per relationship.
  - `record_type`: extraction
  - `anchor_type`: `sec_13f_holding`
  - `anchor_payload`: `{accession_number, cusip, issuer_name, row_indices: [...]}`
  - `anchor_schema_version`: 1
  - `raw_source_row`: JSON of original infotable row(s) for this CUSIP
  - `extraction_method`: automated
  - `confidence`: high
  - Source document: the 13F-HR filing (accession number → source_documents table)
  - Access links: Tier A (SEC EDGAR URL), Tier C (local XML cache)
- **CoverageLog**: filer CIK, report_period, total_holdings_count, extraction_time_ms, filing_date, is_amendment

### Combination report handling

BlackRock example: 30 sub-managers, each reports subset of holdings with own discretion/voting. Same CUSIP appears multiple times.

Strategy:
1. Detect combination report: `len(obj.other_managers) > 0`
2. Create sub-manager entities (type=Fund/InvestmentGroup) with CIK from `other_managers` list
3. Aggregate infotable by CUSIP for the filer-level relationship (total shares, total value)
4. Preserve per-sub-manager breakdown in `detail_payload.sub_managers[]`
5. Create filer→sub-manager relationships (type=parent_company)

### CUSIP→entity resolution (Layer 2 boundary)

13F extractor does NOT resolve CUSIP→entity. It emits stub entities with CUSIP+ticker+issuer_name as external IDs. Layer 2 resolves these stubs to canonical entities via:
1. `entity_external_ids` lookup (CUSIP or ticker → known entity)
2. `config/company_tickers.json` (SEC's CIK↔ticker map) for ticker→CIK→entity
3. Fuzzy match on issuer name as fallback

Extractor emits enough data for Layer 2 to resolve later. Clean boundary — extractor doesn't need to know the entity graph.

### Rate limiting

SEC rate limit: 10 req/sec, `User-Agent` required (INV-16). edgartools handles User-Agent via `set_identity()`. Add throttle wrapper:
- Track request timestamps
- Sleep if approaching 10/sec
- `time.sleep(0.1)` between filers as baseline courtesy (matches recon script)

### Error handling

Per filing:
- edgartools throws → catch, log, emit gap provenance record (`record_type=gap`, `gap_reason`)
- Empty infotable → valid result (filer liquidated or tiny), emit CoverageLog with 0 holdings
- Missing `.infotable_xml` → extract without raw XML anchor, log degraded provenance

Batch level:
- Track success/fail counts
- Never abort batch on single-filer failure
- CoverageLog aggregates to batch summary

### Document cache (INV-42, ADR-0017)

Cache raw XML info table locally at extraction time:
- Path: `data/cache/sec/13f/{cik}/{accession_number}/infotable.xml`
- Access link Tier C points here
- Capture-or-lose: XML cached even if extraction succeeds (INV-38)

## Contracts to define first

`pipeline/contracts.py` currently only has `Entity` started. Before building `thirteenf.py`, need:
- `Relationship` dataclass
- `ProvenanceRecord` dataclass
- `CoverageLog` dataclass
- `ResolutionResult` dataclass
- `ExtractorResult` named tuple or dataclass
- `SourceDocument` dataclass
- `AccessLink` dataclass

These are shared across ALL extractors (Layer 1 common contract). Define once, all extractors import.

## Track

→ `_model/tracks/planned/13f-extractor.md`
