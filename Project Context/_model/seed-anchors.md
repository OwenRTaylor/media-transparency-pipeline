# Starter Outlets — v1 Seed

Reframed 2026-05-19. Prior version (18-anchor 3-tier build order, "100 outlets" target) reversed — see design journal. Old framing replaced because the bulk-fetch mindset conflicted w/ traversal-first arch needed for end-goal URL→answer flow.

## Purpose
v1 seed = test fixtures, not emitted data. Each starter outlet = a category exemplar that exercises a different extraction + traversal path. Goal = prove the automation works across all v1 extractors, surface every kind of trail-end / obscurity / cross-source matching issue early.

Per INV-8 (automation-first), pipeline re-derives every emitted fact from official extraction. Starter outlets guide *where to look*; official extraction is what ships.

## Selection rule (owner-driven)
Owner picks one outlet per category below, after research. Criteria:
- Reach / audience size (Pew lists, Nielsen if available)
- Pipeline-fit (does it exercise the extractor path we need to test?)
- Diversity of structure (varied parent types: dual-class trust, PE-owned, public-co clean chain, opaque private, nonprofit)

## Categories (v1)

| Category | Extractor path | Candidate examples |
|---|---|---|
| Public-co broadcast TV network | FCC LMS + SEC EDGAR | Disney/ABC, Paramount/CBS, Comcast/NBC, Fox |
| Cable news (no FCC license) | SEC EDGAR | Fox News, CNN (WBD), MSNBC (Comcast) |
| Public-co newspaper / digital | SEC EDGAR | NYT, WSJ (NewsCorp), Gannett |
| Private newspaper | Minimal SEC, no FCC, IRS only if nonprofit affiliate | WaPo (Bezos), Cox, Hearst, Advance |
| Local TV / station group | FCC LMS + SEC EDGAR | Sinclair, Nexstar, Gray, Tegna |
| Radio *(conditional)* | FCC LMS + SEC EDGAR | iHeart, Cumulus, Audacy |
| Nonprofit news *(conditional)* | IRS 990 + Schedule R | NPR, PBS, ProPublica |

**Radio + nonprofit conditional** — include only if cheap add-on / difficulty doesn't spike.

**Private newspaper deliberately included.** Under modular arch, near-free to support: traversal layer iterates extractors, logs coverage, trail-end emit. Card visibly shows "ultimate parent: opaque — official sources silent." That **is** the data point (Tenet 1 + Tenet 3).

## Per-outlet starter record
For each picked outlet, owner records in `seed_map.json` (fixture only, not emitted):
- Outlet identifier (callsign / domain / EIN)
- Owner-believed parent chain narrative (for verifying extraction output)
- SEC CIK (if any), FCC FRN(s) (if any), IRS EIN (if any)
- Primary domain(s)
- Expected trail-end (for testing trail-end-honest behavior)

Pipeline runs against this list. Output compared to owner narrative → mismatch flags either bug or outdated narrative.

## Traversal-driven expansion
After starter outlet validated:
1. **Upward trace:** outlet → parent → grandparent → trail-end (Layer 2)
2. **Downward sweep** from each ultimate parent: SEC Exhibit 21 + FCC LMS by-parent-FRN + IRS Schedule R → all owned media entities
3. **Gap detection:** any entity seen as `target` but never reached as `source` → enqueue for next iteration
4. Repeat for next starter outlet

## Display implications (for server card design, not pipeline)
- **"Boring answer" pattern:** dispersed institutional ownership of public co → "No single controlling shareholder. Top institutional holders: Vanguard 9%, BlackRock 7%." Finding, not dead end.
- **Nonprofit pattern:** "governed by board" ≠ "owned by". Show board, not cap table.
- **Opaque pattern (private newspapers, PE shells):** Show trail-end + coverage log ("Queried: SEC ❌, FCC ❌, IRS ❌ — official sources silent past [LLC name]"). Don't paper over.
- **Concentration link:** "Parent controls N other media entities in this database."

## Maintenance
- Review + update starter list on major media M&A
- Quarterly FCC refresh may surface station transfers → reflected via re-running pipeline, not by editing seed map
- Annual SEC refresh → verify extractor still works against starter outlets
