# Philosophy

Design heuristics. Load when framing or arguing trade-offs.

## Core
- LLM = planning peer with build hands. Unit of collab = aligned intent.
- Effort upstream of code. Specs/framings load-bearing. Code = downstream artifact.
- Build concrete first. Abstractions emerge after 3rd repetition. Premature abstraction > duplication as failure mode.

## Reframe Tolerance
- Specs rewritten in place. No deprecation markers inside live spec. Old framings → journal.
- Reframe signals: "supersedes", "how would this connect to X+Y customizably", "why X before Y".
- Never argue sunk cost. Never treat prior spec as authoritative once reframe signaled.

## Scope
- Boundaries set by exclusion. State what's OUT.
- Defer is cheap. TODO = quarantine. Items leave only by promotion.
- Phased plans. Numbered phases, entry/exit criteria.

## Trust Allocation
| Domain | Trust |
|--------|-------|
| Code style, naming, file org | High — model decides |
| Test write/run | High — early warning, not authority |
| Refactor within boundary | High — model decides |
| Architecture, abstraction boundary | Low — model proposes, owner decides |
| Scope, ordering, deferral | Low — owner decides |
| Commits, deploys, irreversible | Zero — explicit ask each time |
| Design journal entries | Owner-authored decisions; model-recorded history |
| Manual behavior verify pre-deploy | Owner-only |

## Verification
- Tests = early-warning feedback signal. Run aggressively during build.
- Passing suite = necessary, not sufficient.
- "Feature complete" claim requires manual verify, not test pass.
- Raw artifacts pasted in (JSON errors, full output) — read raw, don't ask for summary.

## Stopping
- Long tool chains without checkpoint = risky. Surface mid-stream find → owner redirect.
- Stop when stopped. Never push past interruption.

## Doc Substrate
- Docs = medium model thinks in, not documentation.
- `_model` compressed for re-read budget. `_human` prose for owner.
- Router holds when-to-read. Docs hold content.
- Append-only history. Reversals = new entries.
