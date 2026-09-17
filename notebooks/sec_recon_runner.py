"""
Run all callable methods discovered on SEC filing objects (DEF 14A, 10-K, Form 4).
Exploratory — calls each no-arg method, catches errors, reports what's interesting.
"""
from edgar import set_identity, Company
import inspect

set_identity("Owen Taylor owentaylor6075@gmail.com")

company = Company("NYT")

SKIP_PREFIXES = ("__",)
SKIP_NAMES = {"from_filing"}  # classmethod, needs args


def discover_and_call(obj, form_type):
    print(f"\n{'='*80}")
    print(f"  {form_type}: {type(obj).__name__}")
    print(f"{'='*80}")

    # First pass: collect all attrs and callables
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
            preview = repr(val)[:200]
            print(f"  ATTR {name} = {preview}")

    # Second pass: call no-arg methods
    print(f"\n  --- Calling {len(callables)} methods ---")
    for name, method in callables:
        try:
            sig = inspect.signature(method)
            # Check if callable with no args (all params have defaults)
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
            preview = repr(result)[:300]
            print(f"  [call] {name}() => {preview}")
        except Exception as e:
            print(f"  [error] {name}() => {type(e).__name__}: {e}")


for form in ["DEF 14A", "10-K", "4"]:
    try:
        obj = company.get_filings(form=form).latest().obj()
        discover_and_call(obj, form)
    except Exception as e:
        print(f"\n[FAILED] {form}: {e}")
