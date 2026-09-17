"""
13F-HR plumbing script — deeper exploration of edgartools ThirteenF capabilities.

Goals:
1. Reverse lookup: given a media ticker, find institutional holders
2. Test infotable DataFrame structure (columns, dtypes, voting fields)
3. Check feasibility of batch extraction at SEC rate limits
4. Explore other_managers sub-graph for combination reports

Approach: use edgartools to find 13F filers holding FOXA, extract their
holdings data, inspect the structure for pipeline extraction design.

Run: python3 notebooks/sec_13f_plumbing.py
"""
from edgar import set_identity, Company, get_filings, ThirteenF
from edgar import thirteenf
import pandas as pd
import time

set_identity("Owen Taylor owentaylor6075@gmail.com")

TARGET_TICKER = "FOXA"
TARGET_COMPANY = "FOX CORP"


# =============================================================================
# PART 1: Load a known holder's 13F and inspect infotable structure
# =============================================================================
print("=" * 80)
print("PART 1: Infotable structure inspection (Vanguard)")
print("=" * 80)

# Vanguard Group CIK: 0000102909
vanguard = Company("0000102909")
print(f"\nCompany: {vanguard}")

vg_filings = vanguard.get_filings(form="13F-HR")
print(f"13F-HR filings available: {len(vg_filings) if hasattr(vg_filings, '__len__') else '?'}")

vg_latest = vg_filings.latest()
print(f"Latest: {vg_latest}")
print(f"  accession: {vg_latest.accession_number}")
print(f"  filed: {vg_latest.filing_date}")

vg_obj = vg_latest.obj()
print(f"\nThirteenF object type: {type(vg_obj).__name__}")
print(f"  report_period: {vg_obj.report_period}")
print(f"  total_holdings: {vg_obj.total_holdings}")
print(f"  total_value: ${vg_obj.total_value:,.0f}")

# Inspect infotable DataFrame
infotable = vg_obj.infotable
print(f"\n--- infotable DataFrame ---")
print(f"  shape: {infotable.shape}")
print(f"  columns: {list(infotable.columns)}")
print(f"  dtypes:\n{infotable.dtypes}")
print(f"\n  first 3 rows:")
print(infotable.head(3).to_string())

# Also check .holdings DataFrame for comparison
holdings = vg_obj.holdings
print(f"\n--- holdings DataFrame ---")
print(f"  shape: {holdings.shape}")
print(f"  columns: {list(holdings.columns)}")
print(f"\n  first 3 rows:")
print(holdings.head(3).to_string())


# =============================================================================
# PART 2: Filter for target media company in a holder's portfolio
# =============================================================================
print("\n" + "=" * 80)
print(f"PART 2: Find {TARGET_TICKER} in Vanguard's holdings")
print("=" * 80)

# Search by ticker
fox_rows = infotable[infotable["Ticker"] == TARGET_TICKER]
print(f"\nRows matching Ticker=='{TARGET_TICKER}': {len(fox_rows)}")
if len(fox_rows) > 0:
    print(fox_rows.to_string())

# Also search by issuer name (fuzzy)
fox_name_rows = infotable[infotable["Issuer"].str.contains("FOX", case=False, na=False)]
print(f"\nRows matching Issuer contains 'FOX': {len(fox_name_rows)}")
if len(fox_name_rows) > 0:
    print(fox_name_rows.to_string())


# =============================================================================
# PART 3: Reverse lookup — who holds FOXA?
# Strategy: use SEC full-text search or EDGAR company search to find 13F filers
# that report FOXA. edgartools may not support this directly — test alternatives.
# =============================================================================
print("\n" + "=" * 80)
print(f"PART 3: Reverse lookup — who holds {TARGET_TICKER}?")
print("=" * 80)

# Approach A: Check if edgartools has a reverse lookup
print("\nApproach A: Check for reverse-lookup API in edgartools...")
for attr in dir(thirteenf):
    if "hold" in attr.lower() or "owner" in attr.lower() or "reverse" in attr.lower():
        print(f"  thirteenf.{attr}")

# Approach B: Use get_filings to find 13F-HR filings, then filter
# This won't work for reverse lookup — 13F is filed BY the holder, not the held company
# We'd need to either:
#   1. Pre-build an index (batch all 13F filings, extract CUSIPs, build reverse map)
#   2. Use SEC EDGAR full-text search (EFTS) for CUSIP
#   3. Use a known list of major institutional holders and check each

# Approach C: Check a few known major holders for FOXA
print("\nApproach C: Check known major holders for FOXA...")
MAJOR_HOLDERS_CIKS = {
    "Vanguard": "0000102909",
    "BlackRock": "0002012383",
    "State Street": "0000093751",
    "Fidelity (FMR)": "0000315066",
    "Capital Group": "0000036405",
}

results = []
for name, cik in MAJOR_HOLDERS_CIKS.items():
    print(f"\n  Checking {name} (CIK {cik})...")
    try:
        co = Company(cik)
        filing = co.get_filings(form="13F-HR").latest()
        obj = filing.obj()
        it = obj.infotable

        # Search for target
        matches = it[it["Ticker"] == TARGET_TICKER]
        if len(matches) == 0:
            # Try issuer name
            matches = it[it["Issuer"].str.contains(TARGET_COMPANY, case=False, na=False)]

        if len(matches) > 0:
            total_shares = matches["Shares"].sum() if "Shares" in matches.columns else "?"
            total_value = matches["Value"].sum() if "Value" in matches.columns else "?"
            n_entries = len(matches)
            print(f"    FOUND: {n_entries} entries, {total_shares} shares, ${total_value:,.0f} value")
            for _, row in matches.iterrows():
                results.append({
                    "Holder": name,
                    "CIK": cik,
                    "Issuer": row.get("Issuer", "?"),
                    "Class": row.get("Class", "?"),
                    "Cusip": row.get("Cusip", "?"),
                    "Shares": row.get("Shares", "?"),
                    "Value": row.get("Value", "?"),
                    "Period": obj.report_period,
                })
        else:
            print(f"    NOT FOUND in {obj.total_holdings} holdings")

        time.sleep(0.2)  # Rate limit courtesy
    except Exception as e:
        print(f"    ERROR: {type(e).__name__}: {e}")

if results:
    print(f"\n--- Summary: {TARGET_TICKER} institutional holdings ---")
    df = pd.DataFrame(results)
    print(df.to_string())


# =============================================================================
# PART 4: Other managers sub-graph (combination reports)
# =============================================================================
print("\n" + "=" * 80)
print("PART 4: BlackRock other_managers sub-graph")
print("=" * 80)

try:
    blk = Company("0002012383")
    blk_obj = blk.get_filings(form="13F-HR").latest().obj()
    print(f"\nBlackRock other_managers: {len(blk_obj.other_managers)}")
    for mgr in blk_obj.other_managers[:10]:
        print(f"  [{mgr.sequence_number}] {mgr.name} (CIK: {mgr.cik}, File#: {mgr.file_number})")
    if len(blk_obj.other_managers) > 10:
        print(f"  ... +{len(blk_obj.other_managers) - 10} more")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")


# =============================================================================
# PART 5: Feasibility check — timing for batch extraction
# =============================================================================
print("\n" + "=" * 80)
print("PART 5: Timing estimate for batch extraction")
print("=" * 80)

# Time one full extraction (fetch + parse)
start = time.time()
test_co = Company("0000102909")  # Vanguard (large, ~12k holdings)
test_filing = test_co.get_filings(form="13F-HR").latest()
test_obj = test_filing.obj()
_ = test_obj.infotable  # Force parse
elapsed = time.time() - start
print(f"\nSingle extraction (Vanguard, {test_obj.total_holdings} holdings): {elapsed:.1f}s")
print(f"  At this rate:")
print(f"    200 filers: ~{200 * elapsed / 60:.0f} minutes")
print(f"    500 filers: ~{500 * elapsed / 60:.0f} minutes")
print(f"    6000 filers: ~{6000 * elapsed / 60:.0f} minutes ({6000 * elapsed / 3600:.1f} hours)")

print("\n\nDONE.")
