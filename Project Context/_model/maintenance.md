# Maintenance Triggers

Trigger → file matrix.

| Trigger | Update |
|---------|--------|
| End of session | `_model/handoff.md` |
| Milestone mid-session | `_model/handoff.md` |
| New file added | `_model/snapshot.md` |
| Flow / call-graph change | `_model/flows.md` |
| New persisted field | `_model/flows.md` mutable-fields + relevant `_human` data-storage doc |
| New invariant discovered | `INDEX.md` invariants + `_model/flows.md` |
| Architectural decision | `docs/adr.md` |
| Owner design decision | `docs/adr.md` (append-only) |
| Reversal of prior decision | NEW ADR entry referencing original. Never edit old entry. |
| New API surface | `_model/snapshot.md` API section + `_human/API Examples.md` (if owner asks) |
| Feature implemented | `_model/features/<name>.md`. `_human/Features/<name>.md` only on ask. |
| Feature done | `_human/Feature Tracker.md` → Completed |
| Work scoped for build | Create track file in `_model/tracks/planned/` |
| Work started | Move track to `_model/tracks/active/`, update handoff active tracks table |
| Work completed | Mark track status=done, update handoff |
| Design doc written/updated | `_model/design/<name>.md`. Track file points to it, not inline. |

## Never Update For
- Typos
- Comment-only edits
- Behavior-preserving refactors
- Pure renames

## Anti-Patterns (strip on sight)
- "This document describes…", "As mentioned above…", "It is important to note…"
- ASCII diagrams in `_model/`
- Multi-paragraph rationale where fragment works
- Onboarding sections in `_model/`
- "Last updated by" footers
- Status narrative in `CLAUDE.md` (lives in handoff)
- Closing summaries
