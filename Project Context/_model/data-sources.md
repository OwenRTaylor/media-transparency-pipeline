# Data Sources

5 federal DBs + manual inputs. All public, no auth. Canonical detail: [[../external/data-download-checklist.md]].

## 1. FCC LMS (broadcast)
**File:** `Current_LMS_Dump.zip` — pipe-delimited tables, full LMS DB.
**URL:** https://enterpriseefiling.fcc.gov/dataentry/public/tv/lmsDatabase.html
**Schema:** `LMSchema.pdf` + `LM-ERD.pdf` — **reference only, not authority** (Design Journal 2026-05-17). Ground truth = bulk `.dat` shape, verify empirically. PDFs ok for column-name canon, enum hints, FK shape — never final word on type/fill/semantics.
**Scale:** ~12-13k active facilities (TV 1.7k, FM 6.7k, AM 4.5k).
**Cadence:** Quarterly (facility). Biennial (Form 323 ownership, w/ amendments).

**Tables used:**
| Table | Purpose |
|---|---|
| `facility` | Spine. facility_id, call sign, service, channel, city, state, status |
| `ownership_reports_ownership_interest` | **Primary ownership.** Attributable holders + FRNs + voting/equity % |
| `ownership_reports_stations` | filing → facility_id |
| `ownership_reports_application` | Filing date, status, respondent |
| `ownership_reports_respondent_representative_info` | Licensee entity |
| `ownership_reports_contracts` | JSAs, SSAs, LMAs (de-facto control w/o license) |
| `facility_applicant` | facility → licensee |
| `app_party` | Party records w/ FRNs (cross-filing entity refs) |
| `lkp_*` | Decode codes |

**Join path:**
```
facility (facility_id)
  → ownership_reports_stations
    → ownership_reports_application
      → ownership_reports_ownership_interest
```

## 2. SEC EDGAR (public companies)
**Bulk files:**
- `submissions.zip` — filing index per CIK
- `companyfacts.zip` — XBRL facts per CIK (financial well-tagged; ownership inconsistently tagged)
- `company_tickers.json` — ticker ↔ CIK

**Targeted fetches (per media CIK):**
| Form | Purpose | Count |
|---|---|---|
| DEF 14A | Beneficial ownership table, dual-class, trusts | 1 (most recent) |
| 10-K Ex 21 | Subsidiary list — **the bridge to FCC licensees** | 1 (most recent) |
| SC 13G / 13D | 5%+ institutional holders | last 12 mo |

**Filing URL pattern:** `https://www.sec.gov/Archives/edgar/data/{CIK}/{accession-no-with-dashes}/{filename}`
**Rate limit:** 10 req/sec. `User-Agent` header required (app name + contact email).

**Media SIC codes:** 2710, 2711, 2720-2741, 4810-4899, 4832 (radio), 4833 (TV), 4841 (cable), 7812 (motion picture), 7990.

**Tool:** `edgartools` library handles all of this.

## 3. SEC 13F (institutional cross-ownership)
**URL:** https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
**What:** Quarterly bulk. Every $100M+ manager's holdings. Flat: manager CIK, CUSIP, shares, value.
**Why:** DEF 14A/SC 13G cap at 5%+. 13F = full institutional position list. Enables "Vanguard holds 8% Comcast AND 7% Fox AND 9% Disney" — cross-entity concentration.
**Cadence:** Quarterly, +45 days from quarter end.

## 4. SEC Form ADV (PE/HF chains)
**URL:** https://www.sec.gov/foia-services/frequently-requested-documents/form-adv-data
**Why:** PE firms (Alden, Apollo) don't file proxies. ADV Schedule A = direct owners 25%+. Schedule B = indirect owners up to natural persons. Regulatory crack in PE opacity.
**Filter:** PE firms reached via traversal (co-occurrence, ADR-0007); firm name → CRD resolved at runtime against the ADV bulk dataset. No standing `pe_adviser_map` as input (ADR-0010).
**Cadence:** Annual, Mar-Apr.

## 5. IRS 990 (nonprofit media)
**URL:** https://www.irs.gov/charities-non-profits/form-990-series-downloads
**Index:** `https://s3.amazonaws.com/irs-form-990/index_{YEAR}.json` (AWS, stale post-2021 but useful for historical).
**Format:** XML bulk by year/month. Use `lxml` + `irsx`.

**Sections used:**
| Section | Purpose |
|---|---|
| Part VII | Officers, directors, trustees — **primary governance** |
| Schedule R | Related orgs (parent/subsidiary, shared governance) |
| Schedule B | Donors — REDACTED for most 501(c)(3). Limited value. |
| Header | EIN, NTEE code, revenue |

**NTEE filter:** A30 (Media), A31 (Film), A34 (Radio), A38 (TV).
**Alt:** ProPublica API (`https://projects.propublica.org/nonprofits/api/v2/`) — same data, faster for ~50-100 orgs.

## Pipeline input (emitted-affecting)
| File | Content | Maintenance |
|---|---|---|
| `domain_map.json` | Domain → entity. The one authoritative manual input — URL→entity has no official source. Grows one outlet at a time | On expansion / user reports |

## Verification fixtures (NOT emitted — validate resolver/extractor output)
| File | Content | Status |
|---|---|---|
| `seed_map.json` | Owner-verified ground truth for starter outlets: SEC CIK ↔ FCC licensees ↔ FRNs ↔ EIN ↔ CRD ↔ domains | Fixture-only per ADR-0005 |
| `broadcast_group_map.json` | Known-correct FCC group → SEC CIK bridges (top groups) | Verification ledger per ADR-0010; resolver derives these at runtime |
| `pe_adviser_map.json` | Known-correct PE firm → ADV CRD bridges | Verification ledger per ADR-0010; resolver derives at runtime |

## Rate / auth summary
All public, no auth. SEC filing fetches: 10/sec + UA header. Others: no limit on bulk.

## Storage
~5-7 GB downloads. ~25-40 GB unpacked. Few GB working set after filtering.

## NOT sources
Social media, sentiment, inferred connections, news editorial — per [[scope]].

## Future sources (not Phase 1)
[[../external/future-data-sources.md]]. Priority: Wikidata (free, structured, fast win), Form D (private cap raises in EDGAR), OpenCorporates (entity validation).
