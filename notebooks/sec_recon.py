"""
SEC Recon: DEF 14A vs SC 13G side-by-side
Goal: Compare what each form gives us for ownership data.
Target: NYT (New York Times) — dual-class stock, interesting ownership.
"""
from edgar import set_identity, Company

set_identity("Owen Taylor owentaylor6075@gmail.com")

company = Company("NYT")
print(f"{'=' * 70}")
print(f"  Company: {company.name} (CIK: {company.cik})")
print(f"{'=' * 70}\n")


# =====================================================================
#  PART 1: DEF 14A — Proxy Statement
# =====================================================================
print(f"{'#' * 70}")
print(f"  PART 1: DEF 14A (Proxy Statement)")
print(f"{'#' * 70}\n")

filings_14a = company.get_filings(form="DEF 14A")
filing_14a = filings_14a.latest()
print(f"  Filed: {filing_14a.filing_date}  Accession: {filing_14a.accession_no}\n")

proxy = filing_14a.obj()

# Ownership-relevant data
print("--- Beneficial ownership table ---")
bo = getattr(proxy, "beneficial_ownership", None)
if bo is not None and not (hasattr(bo, "empty") and bo.empty):
    print(bo.to_string() if hasattr(bo, "to_string") else bo)
else:
    print("  EMPTY — parser returned no rows")
print()

# Board / governance (maps to governance relationships)
print("--- Director compensation table (= board members) ---")
dct = getattr(proxy, "director_compensation_table", None)
if dct is not None and not (hasattr(dct, "empty") and dct.empty):
    print(dct.to_string() if hasattr(dct, "to_string") else dct)
else:
    print("  EMPTY")
print()

# Executive names (person entities)
print("--- Executive info ---")
print(f"  CEO (PEO): {getattr(proxy, 'peo_name', 'N/A')}")
print(f"  CEO total comp: {getattr(proxy, 'peo_total_comp', 'N/A')}")
print(f"  CEO pay ratio: {getattr(proxy, 'ceo_pay_ratio', 'N/A')}")
ne = getattr(proxy, "named_executives", None)
if ne:
    for ex in ne:
        print(f"  Named exec: {ex}")
else:
    print("  named_executives: EMPTY")
print()

# Voting proposals (shows what shareholders vote on)
print("--- Voting proposals ---")
vp = getattr(proxy, "voting_proposals", None)
if vp:
    for p in vp:
        print(f"  #{p.number}: {p.description[:120]}")
        print(f"         recommendation: {p.board_recommendation}  type: {p.proposal_type}")
else:
    print("  (none)")
print()


# =====================================================================
#  PART 2: SCHEDULE 13G — Beneficial Ownership (>5% holders)
#  NOTE: edgartools needs form="SCHEDULE 13G" not "SC 13G" for .obj()
# =====================================================================
print(f"{'#' * 70}")
print(f"  PART 2: SCHEDULE 13G (Beneficial Ownership >5%)")
print(f"{'#' * 70}\n")

filings_13g = company.get_filings(form="SCHEDULE 13G")
print(f"  Total SCHEDULE 13G filings found: {len(filings_13g)}\n")

# Show recent filings list
print("--- Recent SCHEDULE 13G filings ---")
for f in list(filings_13g)[:10]:
    print(f"  {f.filing_date}  {f.company:40s}  {f.form:20s}  {f.accession_no}")
print()

# Parse each recent filing
for f in list(filings_13g)[:10]:
    print(f"--- Parsing: {f.company} (filed {f.filing_date}) ---")
    try:
        sc = f.obj()
        if sc is None:
            print("  .obj() returned None — parser failed")
            print()
            continue
        print(f"  Object type: {type(sc).__name__}")

        # Issuer info
        issuer = getattr(sc, "issuer_info", None)
        if issuer:
            print(f"  Issuer: {issuer.name}  CUSIP: {getattr(issuer, 'cusip', 'N/A')}")

        # Security info
        sec_info = getattr(sc, "security_info", None)
        if sec_info:
            print(f"  Security: {getattr(sec_info, 'title', 'N/A')}")

        # Total ownership
        print(f"  Total shares: {getattr(sc, 'total_shares', 'N/A')}")
        print(f"  Total percent: {getattr(sc, 'total_percent', 'N/A')}%")

        # Reporting persons (the actual owners)
        persons = getattr(sc, "reporting_persons", [])
        if persons:
            for p in persons:
                print(f"  --- Reporting person ---")
                print(f"    Name:                  {p.name}")
                print(f"    Shares owned:          {getattr(p, 'aggregate_amount', 'N/A')}")
                print(f"    % of class:            {getattr(p, 'percent_of_class', 'N/A')}%")
                print(f"    Sole voting power:     {getattr(p, 'sole_voting_power', 'N/A')}")
                print(f"    Shared voting power:   {getattr(p, 'shared_voting_power', 'N/A')}")
                print(f"    Sole dispositive:      {getattr(p, 'sole_dispositive_power', 'N/A')}")
                print(f"    Shared dispositive:    {getattr(p, 'shared_dispositive_power', 'N/A')}")
        else:
            print("  reporting_persons: EMPTY")

        # Dump remaining attrs for discovery
        print(f"  --- All public attrs ---")
        for attr in sorted(dir(sc)):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(sc, attr)
                if callable(val):
                    continue
                s = repr(val)
                if len(s) > 200:
                    s = s[:200] + "..."
                print(f"    {attr} = {s}")
            except Exception as e:
                print(f"    {attr} — ERROR: {e}")

    except Exception as e:
        print(f"  PARSE ERROR: {e}")
    print()


# =====================================================================
#  SUMMARY: What each form gives us for ownership graph
# =====================================================================
print(f"{'#' * 70}")
print(f"  SUMMARY: Ownership-relevant data by form type")
print(f"{'#' * 70}")
print("""
  DEF 14A (Proxy):
    - Board members (governance relationships, NOT ownership)
    - CEO / named executives (person entities)
    - Beneficial ownership table (>5% + insiders) — BUT often empty via parser
    - Voting proposals (what shareholders decide)
    - Compensation data (rich but not ownership)

  SC 13G (Beneficial Ownership):
    - Who owns >5% (the actual ownership relationships)
    - Share counts + voting/dispositive power breakdown
    - Issuer + CUSIP (entity identifiers)
    - Each filing = one investor's stake in one company
    - Multiple filings per company = multiple large holders
""")