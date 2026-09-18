# Snapshot

Pipeline scaffold created (ADR-0012). 18 docstring-only stub modules — no logic yet. Recon scripts only: `explore_fcc.py` (FCC, working), `notebooks/sec_recon.py` (SEC, retired).

## Repo layout
```
media-transparency-pipeline/
├── CLAUDE.md                  # identity + hard rules (gitignored)
├── Makefile                   # stub stage targets
├── README.md
├── docs/
│   └── adr.md                 # ADR log, git-trackable (ADR-0001..0012)
├── config/
│   └── domain_map.json        # lone authoritative manual input (1 row)
├── pipeline/                  # package — scaffold per ADR-0012
│   ├── contracts.py           # shared dataclasses (stub)
│   ├── resolution/            # names.py urls.py confidence.py (stubs)
│   ├── extractors/            # L1 — __init__ registry; sec/ fcc/ (stubs)
│   │   └── sec/reference/company_tickers.json
│   ├── traversal/             # L2 — url_to_entity.py walk.py (stubs)
│   ├── staging/               # L3 — stage/dedupe/validate/export (stubs)
│   └── run.py                 # entry point (stub)
├── notebooks/
│   └── sec_recon.py           # retired SEC spike — broken paths
├── explore_fcc.py             # FCC LMS exploration script (working, uncommitted)
├── Project Context/           # _model/* + external/* (gitignored)
└── unfiltered_data/           # raw downloads (untracked, large)
```

## Code
| Path | Lines | Role |
|---|---|---|
| `explore_fcc.py` | 276 | FCC LMS exploration — DuckDB views over 4 `.dat` files; 5 query steps (station counts, TV stations, network affiliations, station→owner join, largest groups). Ad-hoc scratch, not pipeline. Uses f-string SQL interpolation. Deferred review. |
| `notebooks/sec_recon.py` | 31 | Retired SEC recon spike. `edgar` SDK — `set_identity`, `Company(cik)`, filings. Conflated all 3 jobs (URL→entity, ticker→CIK, extract). Relative paths to `domain_map.json`/`company_tickers.json` BROKEN after ADR-0012 move. Dead — rewrite clean or delete. |
| `pipeline/**` | 0–5 each | 18 scaffold files, docstring-only. No logic. |
| `Makefile` | 16 | Stub targets: extract/stage/dedupe/validate/export/run. No recipes. |

## Downloaded data
Per `external/data-download-checklist.md`:
- ✅ `Current_LMS_Dump.zip` (~1.6 GB) — FCC LMS full dump
- ✅ `submissions.zip` (~1.5 GB) — SEC filing index by CIK
- ✅ `companyfacts.zip` (~1.4 GB) — SEC XBRL facts per CIK
- ✅ `company_tickers.json` — ticker→CIK lookup → moved to `pipeline/extractors/sec/reference/`
- ✅ FCC `LMSchema.pdf`, `LM-ERD.pdf`, `DA-25-28A1.docx` — reference only, not authority (ADR-0008)
- ✅ SEC 13F bulk — `01dec2025-28feb2026_form13f/` (18 TSV)
- ✅ SEC Form ADV bulk — `adv-filing-data-part1/` (122 CSV) + part2
- ✅ IRS 990 XML — `2026_TEOS_XML_01A/` (12245 XML) + 02A + 03A
- ✅ FCC `323 Spreadsheets/` + `323-E Spreadsheets/` — 10 xlsx (overlap w/ LMS dump TBD)
- Pipeline input: `config/domain_map.json` ✅ (1 row: `nytimes.com → NYT`). Verification fixtures not built (ADR-0005/0010): `seed_map.json` ⬜

**Size rule:** never `Read` whole. Use grep/head slice or streaming script. See CLAUDE.md Hard Rules.

## Git
- Branch: `main`. Commit: `f8ee027` — Initial commit (2026-05-16).
- Untracked: `Makefile`, `config/`, `docs/`, `notebooks/`, `pipeline/`, `explore_fcc.py`, `zip files/`. Modified: `.gitignore`.
- Nothing from the scaffold session committed.

## Next milestones
1. Code `pipeline/contracts.py` — 6 dataclasses (Entity, Relationship, ProvenanceRecord, CoverageLog, ResolutionResult, ExtractorResult). Unblocks all.
2. `resolution/` util stubs — signatures + docstrings.
3. SEC recon spike (NYT only, Jupyter) → real `sec/resolve()` + `extract()`.
4. Thin vertical slice: URL → domain_map → NYT → SEC extractor → queryable SQLite row.
