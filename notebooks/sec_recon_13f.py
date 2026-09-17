"""
13F-HR recon spike — explore edgartools handling of Form 13F-HR filings.

Goals:
1. Load a 13F-HR filing object, discover available methods/attributes
2. Inspect the info table (XML holdings data) structure
3. Check if edgartools parses holdings into structured form (DataFrame?)
4. Compare small filer (Independent Financial Group, 710 entries) vs large (BlackRock, 50k)

Run: python notebooks/sec_recon_13f.py
"""
from edgar import set_identity, Company, get_filings
from edgar import thirteenf
import inspect
import pandas as pd

set_identity("Owen Taylor owentaylor6075@gmail.com")

SKIP_PREFIXES = ("__",)
SKIP_NAMES = {"from_filing"}


def discover_and_call(obj, label, max_result_len=500):
    """Call all no-arg methods on obj, report what's interesting."""
    print(f"\n{'='*80}")
    print(f"  {label}: {type(obj).__name__}")
    print(f"{'='*80}")

    callables = []
    for name in sorted(dir(obj)):
        if any(name.startswith(p) for p in SKIP_PREFIXES):
            continue
        if name in SKIP_NAMES:
            continue
        try:
            val = getattr(obj, name)
        except Exception as e:
            print(f"  [attr-error] {name}: {e}")
            continue

        if callable(val):
            callables.append((name, val))
        else:
            preview = repr(val)[:300]
            print(f"  ATTR {name} = {preview}")

    print(f"\n  --- Calling {len(callables)} methods ---")
    for name, method in callables:
        try:
            sig = inspect.signature(method)
            required = [
                p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty
                and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
            ]
            if required:
                print(f"  [skip] {name}({sig}) — needs args")
                continue
        except (ValueError, TypeError):
            pass

        try:
            result = method()
            preview = repr(result)[:max_result_len]
            print(f"  [call] {name}() => {preview}")
            # If it returns a DataFrame, show shape + columns
            if isinstance(result, pd.DataFrame):
                print(f"         shape={result.shape}, cols={list(result.columns)}")
                if len(result) > 0:
                    print(f"         first row: {result.iloc[0].to_dict()}")
        except Exception as e:
            print(f"  [error] {name}() => {type(e).__name__}: {e}")


# --- Phase 1: Small filer (Independent Financial Group, CIK 275484) ---
print("\n" + "#"*80)
print("# PHASE 1: Small filer — Independent Financial Group (CIK 275484)")
print("#"*80)

try:
    # edgartools Company() accepts CIK as string
    small_co = Company("0000275484")
    print(f"\nCompany('0000275484') => {small_co}")
    filings_13f = small_co.get_filings(form="13F-HR")
    print(f"  13F-HR filings: {filings_13f}")
    filing = filings_13f.latest()
    print(f"\nLatest filing: {filing}")
    print(f"  type: {type(filing).__name__}")
    print(f"  accession: {getattr(filing, 'accession_number', '?')}")
    print(f"  date: {getattr(filing, 'filing_date', '?')}")

    obj = filing.obj()
    discover_and_call(obj, "13F-HR (Independent Financial Group)")
except Exception as e:
    print(f"\n[FAILED] Small filer: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()


# --- Phase 2: BlackRock (CIK 2012383) — large filer, combination report ---
print("\n" + "#"*80)
print("# PHASE 2: Large filer — BlackRock (CIK 2012383)")
print("#"*80)

try:
    blk_co = Company("0002012383")
    print(f"\nCompany('0002012383') => {blk_co}")
    blk_filing = blk_co.get_filings(form="13F-HR").latest()
    print(f"\nLatest filing: {blk_filing}")
    print(f"  accession: {getattr(blk_filing, 'accession_number', '?')}")

    blk_obj = blk_filing.obj()
    discover_and_call(blk_obj, "13F-HR (BlackRock)")
except Exception as e:
    print(f"\n[FAILED] BlackRock: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()


# --- Phase 3: Check if edgartools has a dedicated ThirteenF class ---
print("\n" + "#"*80)
print("# PHASE 3: edgartools module inspection for 13F support")
print("#"*80)

import edgar
for name in sorted(dir(edgar)):
    if "13" in name.lower() or "thirteen" in name.lower() or "holding" in name.lower():
        print(f"  edgar.{name} = {getattr(edgar, name, '?')}")

# Check submodules
try:
    from edgar import thirteenf
    print(f"\n  edgar.thirteenf module exists: {dir(thirteenf)}")
except ImportError:
    print("\n  No edgar.thirteenf module")

try:
    from edgar.holdings import ThirteenF
    print(f"  edgar.holdings.ThirteenF exists")
except ImportError:
    try:
        from edgar import ThirteenF
        print(f"  edgar.ThirteenF exists: {ThirteenF}")
    except ImportError:
        print("  No ThirteenF class found at common import paths")
