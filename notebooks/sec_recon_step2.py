"""
SEC Recon Step 2: Filing-type comparison matrix
For each filing type, check which MVP data points are available and how.

MVP data points:
  1. Entity identity (name, CIK, ticker, share classes)
  2. Ownership relationships (>5% holders, parent/sub)
  3. Subsidiary list (Exhibit 21)
  4. Insider names + roles (officers/directors)
  5. Share structure (classes, outstanding, voting power)

Output: per-filing-type scorecard — present / empty / not-applicable.
"""
from edgar import set_identity, Company

set_identity("Owen Taylor owentaylor6075@gmail.com")

company = Company("NYT")

# --- Helpers ---

def probe(obj, attr_name):
    """Check if an attribute exists and has content. Returns (exists, has_data, sample)."""
    if not hasattr(obj, attr_name):
        return (False, False, None)
    try:
        val = getattr(obj, attr_name)
    except Exception:
        return (True, False, "raised exception")

    if val is None:
        return (True, False, None)
    if hasattr(val, "__len__") and len(val) == 0:
        return (True, False, "empty collection")
    if hasattr(val, "shape") and val.shape[0] == 0:
        return (True, False, "empty dataframe")

    sample = repr(val)[:120]
    return (True, True, sample)


def status_char(exists, has_data):
    if not exists:
        return "—"
    return "✓" if has_data else "∅"


# --- Filing probes ---

results = {}


# DEF 14A
def probe_def14a():
    row = {}
    filing = company.get_filings(form="DEF 14A").latest()
    proxy = filing.obj()

    # Ownership
    e, d, s = probe(proxy, "beneficial_ownership")
    row["ownership_table"] = (status_char(e, d), s)

    # Insider names (directors/officers listed in proxy)
    e, d, s = probe(proxy, "directors")
    row["directors"] = (status_char(e, d), s)
    e, d, s = probe(proxy, "executive_officers")
    row["exec_officers"] = (status_char(e, d), s)
    e, d, s = probe(proxy, "compensation")
    row["compensation"] = (status_char(e, d), s)

    # Share structure
    e, d, s = probe(proxy, "shares_outstanding")
    row["shares_outstanding"] = (status_char(e, d), s)
    e, d, s = probe(proxy, "voting")
    row["voting_info"] = (status_char(e, d), s)

    row["_filing_date"] = str(filing.filing_date)
    return row


# SCHEDULE 13G
def probe_13g():
    row = {}
    filings = company.get_filings(form="SCHEDULE 13G")
    row["_count"] = len(filings)
    if len(filings) == 0:
        return row

    filing = filings.latest()
    sc = filing.obj()

    e, d, s = probe(sc, "reporting_persons")
    row["reporting_persons"] = (status_char(e, d), s)
    e, d, s = probe(sc, "percent_of_class")
    row["percent_of_class"] = (status_char(e, d), s)
    e, d, s = probe(sc, "shares_beneficially_owned")
    row["shares_owned"] = (status_char(e, d), s)
    e, d, s = probe(sc, "subject_company")
    row["subject_company"] = (status_char(e, d), s)

    row["_filing_date"] = str(filing.filing_date)
    return row


# SCHEDULE 13D
def probe_13d():
    row = {}
    filings = company.get_filings(form="SCHEDULE 13D")
    row["_count"] = len(filings)
    if len(filings) == 0:
        return row

    filing = filings.latest()
    sc = filing.obj()

    e, d, s = probe(sc, "reporting_persons")
    row["reporting_persons"] = (status_char(e, d), s)
    e, d, s = probe(sc, "percent_of_class")
    row["percent_of_class"] = (status_char(e, d), s)
    e, d, s = probe(sc, "purpose_of_transaction")
    row["purpose"] = (status_char(e, d), s)

    row["_filing_date"] = str(filing.filing_date)
    return row


# FORM 3 (insider initial)
def probe_form3():
    row = {}
    filings = company.get_filings(form="3")
    row["_count"] = len(filings)
    if len(filings) == 0:
        return row

    filing = filings.latest()
    obj = filing.obj()
    if obj is None:
        row["_parse_failed"] = True
        return row

    e, d, s = probe(obj, "reporting_owner")
    row["reporting_owner"] = (status_char(e, d), s)
    e, d, s = probe(obj, "issuer")
    row["issuer"] = (status_char(e, d), s)
    e, d, s = probe(obj, "non_derivative_holdings")
    row["non_deriv_holdings"] = (status_char(e, d), s)
    e, d, s = probe(obj, "derivative_holdings")
    row["deriv_holdings"] = (status_char(e, d), s)
    e, d, s = probe(obj, "relationship")
    row["relationship"] = (status_char(e, d), s)

    row["_filing_date"] = str(filing.filing_date)
    return row


# FORM 4 (insider changes)
def probe_form4():
    row = {}
    filings = company.get_filings(form="4")
    row["_count"] = len(filings)
    if len(filings) == 0:
        return row

    filing = filings.latest()
    obj = filing.obj()
    if obj is None:
        row["_parse_failed"] = True
        return row

    e, d, s = probe(obj, "reporting_owner")
    row["reporting_owner"] = (status_char(e, d), s)
    e, d, s = probe(obj, "issuer")
    row["issuer"] = (status_char(e, d), s)
    e, d, s = probe(obj, "non_derivative_transactions")
    row["non_deriv_transactions"] = (status_char(e, d), s)
    e, d, s = probe(obj, "derivative_transactions")
    row["deriv_transactions"] = (status_char(e, d), s)
    e, d, s = probe(obj, "relationship")
    row["relationship"] = (status_char(e, d), s)

    row["_filing_date"] = str(filing.filing_date)
    return row


# 10-K (Exhibit 21 = subsidiaries)
def probe_10k():
    row = {}
    filings = company.get_filings(form="10-K")
    row["_count"] = len(filings)
    if len(filings) == 0:
        return row

    filing = filings.latest()
    obj = filing.obj()

    # Subsidiary list via Exhibit 21
    attachments = getattr(obj, "attachments", None) or getattr(filing, "attachments", None)
    has_ex21 = False
    if attachments and hasattr(attachments, "__iter__"):
        for a in attachments:
            desc = getattr(a, "description", "") or ""
            doc = getattr(a, "document", "") or ""
            if "21" in doc or "subsidiar" in desc.lower():
                has_ex21 = True
                break
    row["exhibit_21"] = ("✓" if has_ex21 else "∅", "found in attachments" if has_ex21 else "not found")

    # Entity info from 10-K
    e, d, s = probe(obj, "company")
    row["company_name"] = (status_char(e, d), s)
    e, d, s = probe(obj, "period_of_report")
    row["period"] = (status_char(e, d), s)

    row["_filing_date"] = str(filing.filing_date)
    return row


# XBRL Company Facts (share classes)
def probe_xbrl():
    row = {}
    facts = company.get_facts()

    target_concepts = [
        "CommonStockSharesOutstanding",
        "CommonStockSharesAuthorized",
        "CommonStockVotesPerShare",
        "StockholdersEquity",
    ]

    for concept in target_concepts:
        try:
            val = facts[concept]
            has_data = val is not None and (not hasattr(val, "__len__") or len(val) > 0)
            row[concept] = ("✓" if has_data else "∅", repr(val)[:80] if has_data else None)
        except (KeyError, IndexError, TypeError):
            row[concept] = ("—", "not in facts")
        except Exception as e:
            row[concept] = ("!", str(e)[:80])

    return row


# --- Run all probes ---

print(f"{'=' * 70}")
print(f"  SEC RECON STEP 2 — Filing Data-Point Matrix for {company.name}")
print(f"{'=' * 70}\n")

probe_funcs = [
    ("DEF 14A", probe_def14a),
    ("SCHEDULE 13G", probe_13g),
    ("SCHEDULE 13D", probe_13d),
    ("FORM 3", probe_form3),
    ("FORM 4", probe_form4),
    ("10-K", probe_10k),
    ("XBRL Facts", probe_xbrl),
]

for name, func in probe_funcs:
    print(f"\n{'─' * 50}")
    print(f"  {name}")
    print(f"{'─' * 50}")
    try:
        row = func()
        for key, val in row.items():
            if key.startswith("_"):
                print(f"    [{key}] {val}")
            else:
                status, sample = val
                sample_str = f"  → {sample}" if sample else ""
                print(f"    {status} {key}{sample_str}")
    except Exception as e:
        print(f"    ERROR: {e}")


# --- Summary matrix ---

print(f"\n\n{'=' * 70}")
print("  SUMMARY: What gives us what?")
print(f"{'=' * 70}")
print("""
  MVP Data Point          → Best Source(s)
  ─────────────────────────────────────────────────────
  Entity identity         → Company object (name, CIK, ticker always available)
  >5% holders (passive)   → SCHEDULE 13G (reporting_persons + percent)
  >5% holders (activist)  → SCHEDULE 13D (same shape, adds purpose)
  Subsidiary list         → 10-K Exhibit 21 (attachment, needs HTML parse)
  Insider names/roles     → FORM 3 (initial) + FORM 4 (changes)
  Share classes/outstanding → XBRL facts (if concept tagged) + DEF 14A
  Voting power per class  → NOT in structured data (ADR-0014: deferred to v2)
  Beneficial ownership %  → DEF 14A table (IF edgartools parses it — currently empty)
""")
