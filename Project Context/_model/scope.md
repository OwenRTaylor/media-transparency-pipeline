# Scope — Phase 1

## Thesis
"It's just people." Behind every outlet → real people exercise control. Make those chains trivial to inspect via public records. Where chain dies → say so explicitly. Murkiness = signal, not failure. (Tenet 1.)

## Pipeline goal (this repo)
Bulk-data → SQLite. Server (separate Node.js repo) reads SQLite, renders answer cards. SQLite file = contract between systems.

Architecture: modular three-layer (Layer 1 extractors + Layer 2 traversal + Layer 3 stage/export). Layer 2 designed to also serve end-goal URL→answer flow post-v1 — not a re-architecture later. See `_model/data-model.md`.

## v1 seed (locked 2026-05-19)
**One outlet per category**, owner-picked after reach/audience research. v1 = prove the automation works across every extraction path; expansion is iterative.

Categories:
- Public-co broadcast TV network (Disney/ABC, Paramount/CBS, Comcast/NBC, Fox)
- Cable news / no-FCC-license (Fox News, CNN, MSNBC)
- Public-co newspaper / digital (NYT, WSJ via NewsCorp, Gannett)
- Private newspaper (WaPo, Cox, Hearst) — included to expose obscurity-as-data
- Local TV / station group (Sinclair, Nexstar, Gray)
- Radio (iHeart, Cumulus, Audacy) — *conditional: include if cheap add-on*
- Nonprofit news (NPR, PBS, ProPublica) — *conditional: include if difficulty doesn't spike*

Owner picks specific outlets after research; this doc lists the categories + candidate examples only.

## Expansion
Test starter outlet end-to-end → fix issues → next outlet → repeat. Outward sweep:
1. Upward trace each starter → ultimate parent (trail-end honest where official sources die)
2. Downward sweep from each ultimate parent → every owned media entity in official sources
3. Gap-detection second pass — entities that appeared as `target` but never reached as `source` → enqueue
4. Manual coverage audit against external lists (Pew, etc.) — used only as audit, not data

## Exit conditions (two axes — orthogonal)
- **Structural completion:** all v1 extractors working, Layer 2 traversal walking, provenance captured per fact, validation + export idempotent, server consumes SQLite cleanly.
- **Coverage completion:** "most of American media" — owner judgment call, no fixed number.

Either reached = move to website build, then end-goal interactive feature.

## What an outlet entity must have
- ≥1 first-order ownership chain (outlet → parent), automated-from-official-source
- Relationship type classification (see `data-model.md` taxonomy)
- Provenance per link w/ granular `source_anchor` (Tenet 3)
- Explicit marker where chain cannot extend further (`unknown_opaque` w/ coverage log)

## Success signal (qualitative, not quotas)
- Cards distinguish types: "owned by" ≠ "major shareholder of" ≠ "funded by" ≠ "governed by"
- Trail-end honest: "trail ends at X — no further records" visible, not hidden
- Private newspaper card visibly demonstrates obscurity-as-data
- Every emitted fact has a working link back to a primary-source row (Tenet 3)

## OUT of Phase 1
- LLM extraction (v2+)
- Unofficial / non-publisher-of-record sources (v2+)
- International outlets
- Podcasts, newsletters, individual creators
- Social media accounts as outlets
- Real-time / article-level analysis
- Multi-hop resolution past 2 hops
- Temporal ownership tracking beyond name-change events
- Feed / explore UI
- Browser extension
- Bias / editorial influence quantification
- Cold-path API fallback (live SEC/FCC calls at query time)
- Server-side write-back to pipeline DB (end-goal feature, deferred)

All deferred items → [[../external/news-transparency-extended-vision]]. Schema must support but not implement.

## NOT a data source (v1)
- Social media mentions
- Sentiment / editorial analysis
- Privately held informal-relationship info
- Inferred / speculated connections
- Any source not linkable to a public-record primary source

## Prior framing
Earlier scope target was "~100 outlets / 18 anchor parent entities". Reversed 2026-05-19 — see design journal.
