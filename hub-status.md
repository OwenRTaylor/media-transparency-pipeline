# Media Transparency Pipeline — Hub Status
Generated: 2026-09-17 (source handoff 2026-07-11)

Data pipeline investigating media ownership and political ad spending. Pulls from FCC and SEC public data sources; strict source-extraction/provenance discipline (ADR log).

## State
Active implementation. Branch `main`. Entity-discovery pipeline running; iterating on cross-source match accuracy. Uncommitted discovery subsystem + ADRs 0018–0022.

## Active
- **Entity discovery** — D1 SEC SIC scan (1,267 candidates) + D2 FCC LMS scan (135,640) done. D3 cross-source overlap v1 complete: fuzzy SEC↔FCC match → 369 high / 9,344 medium / 1,504 low, ~2% false-positive in high tier, 16/18 anchors found. Iterating toward high confidence.

## Planned (scoping)
- 13F extractor — paused.

## Next
Improve match accuracy: (1) check FCC LMS EIN field for a deterministic bridge, (2) address matching to promote medium→high, (3) Haiku LLM judge on medium+high pairs (~$0.07), (4) repeat until high-tier false-positive ≈ 0.
