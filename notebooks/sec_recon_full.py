"""
SEC Recon Step 1: Full filing-type survey
Target: NYT — grab ALL data from every relevant filing type, no filtering.
Purpose: See what edgartools gives us per form before deciding what matters for MVP.

MVP scope reminder: current ownership + parent/subsidiary traversal.
Historical ownership changes = out of scope.
"""
from edgar import set_identity, Company
import traceback

set_identity("Owen Taylor owentaylor6075@gmail.com")

company = Company("NYT")
print(f"{'=' * 70}")
print(f"  Company: {company.name} (CIK: {company.cik})")
print(f"{'=' * 70}\n")


def dump_attrs(obj, indent=2):
    """Dump all public non-callable attributes of an object."""
    prefix = " " * indent
    for attr in sorted(dir(obj)):
        if attr.startswith("_"):
            continue
        try:
            val = getattr(obj, attr)
            if callable(val):
                continue
            s = repr(val)
            if len(s) > 300:
                s = s[:300] + "..."
            print(f"{prefix}{attr} = {s}")
        except Exception as e:
            print(f"{prefix}{attr} — ERROR: {e}")


def section(title):
    print(f"\n{'#' * 70}")
    print(f"  {title}")
    print(f"{'#' * 70}\n")


# =====================================================================
#  DEF 14A — Proxy Statement
# =====================================================================
section("DEF 14A (Proxy Statement)")

try:
    filings_14a = company.get_filings(form="DEF 14A")
    filing_14a = filings_14a.latest()
    print(f"  Filed: {filing_14a.filing_date}  Accession: {filing_14a.accession_no}")
    proxy = filing_14a.obj()
    print(f"  Object type: {type(proxy).__name__}\n")
    print("--- ALL ATTRIBUTES ---")
    dump_attrs(proxy)
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  DEF 14A — Beneficial Ownership Table (explicit re-test)
#  Last recon: beneficial_ownership was EMPTY. edgartools may have fixed.
# =====================================================================
section("DEF 14A — beneficial_ownership table (re-test)")

try:
    filings_14a = company.get_filings(form="DEF 14A")
    filing_14a = filings_14a.latest()
    proxy = filing_14a.obj()

    bo = getattr(proxy, "beneficial_ownership", None)
    print(f"  beneficial_ownership type: {type(bo).__name__}")
    print(f"  beneficial_ownership value: {repr(bo)}")

    if bo is not None and hasattr(bo, "__len__"):
        print(f"  Length: {len(bo)}")

    if hasattr(bo, "columns"):
        print(f"  Columns: {list(bo.columns)}")
        print(f"  Shape: {bo.shape}")
        print(f"\n  First rows:")
        print(bo.head(10).to_string(index=False))
    elif hasattr(bo, "__iter__") and bo:
        print(f"\n  First items:")
        for i, item in enumerate(bo):
            if i >= 5:
                print(f"    ... ({len(list(bo)) - 5} more)")
                break
            print(f"    [{i}] {repr(item)}")
            if hasattr(item, "__dict__"):
                dump_attrs(item, indent=6)

    # Also check for any other ownership-related attrs we might have missed
    ownership_attrs = [a for a in dir(proxy) if "owner" in a.lower() or "beneficial" in a.lower() or "voting" in a.lower()]
    if ownership_attrs:
        print(f"\n  Ownership-related attributes found: {ownership_attrs}")
        for a in ownership_attrs:
            try:
                val = getattr(proxy, a)
                if not callable(val):
                    s = repr(val)
                    if len(s) > 500:
                        s = s[:500] + "..."
                    print(f"    {a} = {s}")
            except Exception as e:
                print(f"    {a} — ERROR: {e}")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  SCHEDULE 13G — Beneficial Ownership (passive, >5%)
#  Already spot-checked — include latest only for side-by-side
# =====================================================================
section("SCHEDULE 13G (latest only — already spot-checked)")

try:
    filings_13g = company.get_filings(form="SCHEDULE 13G")
    f = filings_13g.latest()
    print(f"  Filed: {f.filing_date}  Accession: {f.accession_no}")
    print(f"  Total 13G filings: {len(filings_13g)}")
    sc = f.obj()
    print(f"  Object type: {type(sc).__name__}\n")
    print("--- ALL ATTRIBUTES ---")
    dump_attrs(sc)
    if hasattr(sc, "reporting_persons"):
        for i, p in enumerate(sc.reporting_persons):
            print(f"\n  --- reporting_person[{i}] ---")
            dump_attrs(p, indent=4)
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  SCHEDULE 13D — Beneficial Ownership (activist, >5%)
# =====================================================================
section("SCHEDULE 13D (Activist >5% holders)")

try:
    filings_13d = company.get_filings(form="SCHEDULE 13D")
    print(f"  Total 13D filings: {len(filings_13d)}")
    if len(filings_13d) > 0:
        f = filings_13d.latest()
        print(f"  Latest filed: {f.filing_date}  Accession: {f.accession_no}")
        sc = f.obj()
        print(f"  Object type: {type(sc).__name__}\n")
        print("--- ALL ATTRIBUTES ---")
        dump_attrs(sc)
        if hasattr(sc, "reporting_persons"):
            for i, p in enumerate(sc.reporting_persons):
                print(f"\n  --- reporting_person[{i}] ---")
                dump_attrs(p, indent=4)
    else:
        print("  No 13D filings found for this company.")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  FORM 3 — Initial Statement of Beneficial Ownership (insiders)
# =====================================================================
section("FORM 3 (Initial insider ownership)")

try:
    filings_3 = company.get_filings(form="3")
    print(f"  Total Form 3 filings: {len(filings_3)}")
    if len(filings_3) > 0:
        for f in list(filings_3)[:3]:
            print(f"\n  --- Filing: {f.filing_date}  {f.company}  Accession: {f.accession_no} ---")
            try:
                obj = f.obj()
                if obj is None:
                    print("    .obj() returned None")
                    continue
                print(f"    Object type: {type(obj).__name__}")
                dump_attrs(obj, indent=4)
            except Exception as e:
                print(f"    PARSE ERROR: {e}")
    else:
        print("  No Form 3 filings found.")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  FORM 4 — Changes in Beneficial Ownership (insider transactions)
# =====================================================================
section("FORM 4 (Insider ownership changes)")

try:
    filings_4 = company.get_filings(form="4")
    print(f"  Total Form 4 filings: {len(filings_4)}")
    if len(filings_4) > 0:
        for f in list(filings_4)[:3]:
            print(f"\n  --- Filing: {f.filing_date}  {f.company}  Accession: {f.accession_no} ---")
            try:
                obj = f.obj()
                if obj is None:
                    print("    .obj() returned None")
                    continue
                print(f"    Object type: {type(obj).__name__}")
                dump_attrs(obj, indent=4)
            except Exception as e:
                print(f"    PARSE ERROR: {e}")
    else:
        print("  No Form 4 filings found.")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  FORM 5 — Annual Statement of Beneficial Ownership
# =====================================================================
section("FORM 5 (Annual insider ownership)")

try:
    filings_5 = company.get_filings(form="5")
    print(f"  Total Form 5 filings: {len(filings_5)}")
    if len(filings_5) > 0:
        f = filings_5.latest()
        print(f"  Latest filed: {f.filing_date}  Accession: {f.accession_no}")
        try:
            obj = f.obj()
            if obj is None:
                print("    .obj() returned None")
            else:
                print(f"    Object type: {type(obj).__name__}")
                dump_attrs(obj, indent=4)
        except Exception as e:
            print(f"    PARSE ERROR: {e}")
    else:
        print("  No Form 5 filings found.")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  10-K — Annual Report (Exhibit 21 = subsidiary list)
# =====================================================================
section("10-K (Annual Report — subsidiaries, structure)")

try:
    filings_10k = company.get_filings(form="10-K")
    print(f"  Total 10-K filings: {len(filings_10k)}")
    if len(filings_10k) > 0:
        f = filings_10k.latest()
        print(f"  Latest filed: {f.filing_date}  Accession: {f.accession_no}")
        obj = f.obj()
        print(f"  Object type: {type(obj).__name__}\n")
        print("--- ALL ATTRIBUTES ---")
        dump_attrs(obj)

        # Try to find Exhibit 21 (subsidiary list)
        print("\n--- EXHIBIT 21 (subsidiaries) ---")
        exhibits = getattr(obj, "exhibits", None)
        if exhibits:
            print(f"  Exhibits type: {type(exhibits).__name__}")
            # Try to find exhibit 21
            ex21 = None
            if hasattr(exhibits, "__getitem__"):
                try:
                    ex21 = exhibits[21]
                except (KeyError, IndexError, TypeError):
                    pass
                try:
                    ex21 = exhibits["21"]
                except (KeyError, IndexError, TypeError):
                    pass
            if ex21:
                print(f"  Exhibit 21 found: {type(ex21).__name__}")
                dump_attrs(ex21, indent=4)
            else:
                print("  Exhibit 21 not found via indexing. Dumping all exhibits:")
                dump_attrs(exhibits, indent=4)
        else:
            print("  No exhibits attribute found.")

        # Try attachments (alternate way edgartools exposes documents)
        print("\n--- ATTACHMENTS ---")
        attachments = getattr(obj, "attachments", None) or getattr(f, "attachments", None)
        if attachments:
            print(f"  Type: {type(attachments).__name__}")
            if hasattr(attachments, "__iter__"):
                for a in list(attachments)[:15]:
                    print(f"    {getattr(a, 'description', '?'):50s}  {getattr(a, 'document', '?')}")
        else:
            print("  No attachments found.")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  8-K — Current Report (M&A, change of control, material events)
# =====================================================================
section("8-K (Current Report — material events)")

try:
    filings_8k = company.get_filings(form="8-K")
    print(f"  Total 8-K filings: {len(filings_8k)}")
    if len(filings_8k) > 0:
        # Grab latest 5 — 8-Ks vary widely, need a few to see the shape
        for f in list(filings_8k)[:5]:
            print(f"\n  --- 8-K: {f.filing_date}  Accession: {f.accession_no} ---")
            try:
                obj = f.obj()
                if obj is None:
                    print("    .obj() returned None")
                    continue
                print(f"    Object type: {type(obj).__name__}")
                dump_attrs(obj, indent=4)
            except Exception as e:
                print(f"    PARSE ERROR: {e}")
    else:
        print("  No 8-K filings found.")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  S-1 / F-1 — Registration (IPO prospectus, cap table)
# =====================================================================
section("S-1 / F-1 (Registration / IPO)")

for form_type in ["S-1", "F-1"]:
    try:
        filings = company.get_filings(form=form_type)
        print(f"  {form_type}: {len(filings)} filings found")
        if len(filings) > 0:
            f = filings.latest()
            print(f"  Latest filed: {f.filing_date}  Accession: {f.accession_no}")
            try:
                obj = f.obj()
                if obj is None:
                    print("    .obj() returned None")
                else:
                    print(f"    Object type: {type(obj).__name__}")
                    dump_attrs(obj, indent=4)
            except Exception as e:
                print(f"    PARSE ERROR: {e}")
    except Exception as e:
        print(f"  {form_type} ERROR: {e}")
    print()


# =====================================================================
#  13F-HR — NOTE: Filed by INVESTORS, not by this company.
#  Can't get via company.get_filings(). Different access pattern.
#  Leaving this as a flag — needs separate approach.
# =====================================================================
section("13F-HR (Institutional Holdings) — ACCESS NOTE")
print("""  13F-HR filings are submitted by investment managers, NOT by the company.
  To find who holds NYT stock via 13F, you'd search from the investor side
  (e.g., Berkshire Hathaway's 13F lists all their holdings including NYT).

  This is the INVERSE of 13G/13D — same data, different filer.
  For MVP traversal: 13G/13D already gives us >5% holders.
  13F adds the long tail of institutional holders (often <5%).

  Access pattern TBD — not available via Company("NYT").get_filings().
""")


# =====================================================================
#  XBRL Company Facts — voting rights per share class
#  Research says 10-K XBRL contains CommonStockVotesPerShare per class.
#  Testing: does get_facts() return per-class dimensional data?
# =====================================================================
section("XBRL COMPANY FACTS — voting rights + share classes")

try:
    facts = company.get_facts()
    print(f"  get_facts() type: {type(facts).__name__}")

    if hasattr(facts, "columns"):
        print(f"  Shape: {facts.shape}")
        print(f"  Columns: {list(facts.columns)}")
    elif hasattr(facts, "__len__"):
        print(f"  Length: {len(facts)}")

    # Search for voting-related concepts
    voting_keywords = ["vote", "voting", "class", "commonstock"]
    print(f"\n--- Searching for voting/class-related XBRL concepts ---")

    if hasattr(facts, "columns") and hasattr(facts, "iterrows"):
        # DataFrame-like: filter rows
        for kw in voting_keywords:
            mask = facts.apply(lambda row: row.astype(str).str.contains(kw, case=False).any(), axis=1)
            matches = facts[mask]
            if len(matches) > 0:
                print(f"\n  Keyword '{kw}': {len(matches)} matches")
                print(matches.to_string())
    elif hasattr(facts, "filter"):
        # edgartools CompanyFacts object — try filter method
        for kw in voting_keywords:
            try:
                filtered = facts.filter(kw)
                if filtered is not None and len(filtered) > 0:
                    print(f"\n  Keyword '{kw}': {len(filtered)} matches")
                    print(repr(filtered)[:2000])
            except Exception as e:
                print(f"  filter('{kw}') error: {e}")
    else:
        # Unknown shape — dump what we can
        print(f"  Unknown facts structure. Attrs:")
        dump_attrs(facts)

    # Direct concept lookups
    target_concepts = [
        "CommonStockVotesPerShare",
        "CommonStockSharesOutstanding",
        "CommonStockSharesAuthorized",
        "StockholdersEquity",
    ]
    print(f"\n--- Direct concept lookups ---")
    for concept in target_concepts:
        try:
            if hasattr(facts, "__getitem__"):
                val = facts[concept]
                print(f"  {concept}: {repr(val)[:500]}")
            elif hasattr(facts, "get"):
                val = facts.get(concept)
                print(f"  {concept}: {repr(val)[:500]}")
            else:
                print(f"  {concept}: can't index into facts object")
                break
        except (KeyError, IndexError, TypeError) as e:
            print(f"  {concept}: not found ({e})")
        except Exception as e:
            print(f"  {concept}: ERROR {e}")

except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()


# =====================================================================
#  Company-level attributes (what edgartools knows about the entity)
# =====================================================================
section("COMPANY OBJECT — entity-level attributes")
print("--- ALL ATTRIBUTES ---")
dump_attrs(company)


print(f"\n{'=' * 70}")
print("  STEP 1 COMPLETE — raw dump of all filing types for NYT")
print(f"{'=' * 70}")
