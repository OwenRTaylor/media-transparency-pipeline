#!/usr/bin/env python3
"""D3: Cross-source overlap — SEC SIC candidates vs FCC LMS candidates.

Dedupes each list by normalized name, then fuzzy-matches across sources.
Both full candidate lists carry forward to D4 regardless of match status.
This script measures overlap and produces bridge evidence for entity resolution.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz, process

DISCOVERY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "discovery"
SEC_FILE = DISCOVERY_DIR / "sec_media_candidates.json"
FCC_FILE = DISCOVERY_DIR / "fcc_media_candidates.json"
OUTPUT_FILE = DISCOVERY_DIR / "cross_source_matches.json"
SUMMARY_FILE = DISCOVERY_DIR / "cross_source_summary.json"

SUFFIX_PATTERNS = [
    r",?\s+LLC\.?$",
    r",?\s+L\.L\.C\.?$",
    r",?\s+INC\.?$",
    r",?\s+INCORPORATED$",
    r",?\s+CORP\.?$",
    r",?\s+CORPORATION$",
    r",?\s+LTD\.?$",
    r",?\s+LIMITED$",
    r",?\s+L\.P\.?$",
    r",?\s+LP$",
    r",?\s+CO\.?$",
    r",?\s+DEBTOR-IN-POSSESSION$",
]
SUFFIX_RE = re.compile("|".join(SUFFIX_PATTERNS), re.IGNORECASE)

DOMAIN_WORDS = frozenset({
    "BROADCASTING", "BROADCAST", "COMMUNICATIONS", "COMMUNICATION",
    "MEDIA", "TELEVISION", "TV", "RADIO", "ENTERTAINMENT",
    "HOLDINGS", "GROUP", "COMPANY", "ENTERPRISES", "NETWORKS",
    "NETWORK", "LICENSEE", "LICENSE", "STATIONS", "PARTNERS",
})


def distinctive_tokens(normalized_name: str) -> set[str]:
    """Tokens that carry identity — excludes common domain words."""
    return {t for t in normalized_name.split() if t not in DOMAIN_WORDS and len(t) > 1}


def normalize(name: str) -> str:
    n = name.upper().strip()
    if n.startswith("THE "):
        n = n[4:]
    prev = None
    while n != prev:
        prev = n
        n = SUFFIX_RE.sub("", n).strip()
    n = re.sub(r"\s+", " ", n).strip()
    return n


def blocking_key(normalized_name: str) -> str:
    """First significant token (skip single-char tokens)."""
    tokens = normalized_name.split()
    for t in tokens:
        if len(t) > 1:
            return t[:4]
    return normalized_name[:4] if normalized_name else ""


def dedupe_sec(records: list[dict]) -> dict[str, list[dict]]:
    """Group SEC records by normalized name. Returns {norm_name: [records]}."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[normalize(r["name"])].append(r)
    return dict(groups)


def dedupe_fcc(records: list[dict]) -> dict[str, list[dict]]:
    """Group FCC records by normalized name. Returns {norm_name: [records]}."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[normalize(r["licensee_name"])].append(r)
    return dict(groups)


def build_blocks(names: list[str]) -> dict[str, list[str]]:
    """Group normalized names by blocking key."""
    blocks: dict[str, list[str]] = defaultdict(list)
    for name in names:
        blocks[blocking_key(name)].append(name)
    return dict(blocks)


def find_matches(
    sec_names: list[str],
    fcc_names: list[str],
    score_cutoff: int = 50,
) -> list[dict]:
    """Fuzzy match SEC names against FCC names using blocking."""
    fcc_blocks = build_blocks(fcc_names)
    fcc_name_set = set(fcc_names)

    sec_blocks_map: dict[str, list[str]] = defaultdict(list)
    for name in sec_names:
        sec_blocks_map[blocking_key(name)].append(name)

    all_fcc_names_list = list(fcc_name_set)
    matches = []
    seen_pairs: set[tuple[str, str]] = set()

    for sec_name in sec_names:
        sec_key = blocking_key(sec_name)

        candidates = set()
        if sec_key in fcc_blocks:
            candidates.update(fcc_blocks[sec_key])

        sec_tokens = sec_name.split()
        for token in sec_tokens:
            if len(token) > 1:
                tk = token[:4]
                if tk in fcc_blocks:
                    candidates.update(fcc_blocks[tk])

        if not candidates:
            continue

        candidate_list = list(candidates)
        results = process.extract(
            sec_name,
            candidate_list,
            scorer=fuzz.WRatio,
            score_cutoff=score_cutoff,
            limit=10,
        )

        sec_dist = distinctive_tokens(sec_name)

        for fcc_name, score, _ in results:
            pair = (sec_name, fcc_name)
            if pair not in seen_pairs:
                seen_pairs.add(pair)

                fcc_dist = distinctive_tokens(fcc_name)
                if sec_dist and fcc_dist:
                    shared = sec_dist & fcc_dist
                    smaller = min(len(sec_dist), len(fcc_dist))
                    overlap_frac = len(shared) / smaller if smaller else 0
                    shared_count = len(shared)
                else:
                    overlap_frac = 0.0
                    shared_count = 0

                if score >= 97 and overlap_frac >= 0.5 and shared_count >= 1:
                    tier = "high"
                elif score >= 90 and overlap_frac >= 0.75 and shared_count >= 2:
                    tier = "high"
                elif score >= 70:
                    tier = "medium"
                else:
                    tier = "low"

                matches.append({
                    "sec_name_normalized": sec_name,
                    "fcc_name_normalized": fcc_name,
                    "score": round(score, 1),
                    "tier": tier,
                    "distinctive_overlap": round(overlap_frac, 3),
                })

    return sorted(matches, key=lambda m: -m["score"])


def enrich_matches(
    matches: list[dict],
    sec_groups: dict[str, list[dict]],
    fcc_groups: dict[str, list[dict]],
) -> list[dict]:
    """Add source record details (CIKs, FRNs, original names) to matches."""
    enriched = []
    for m in matches:
        sec_recs = sec_groups[m["sec_name_normalized"]]
        fcc_recs = fcc_groups[m["fcc_name_normalized"]]

        enriched.append({
            **m,
            "sec_original_names": list({r["name"] for r in sec_recs}),
            "sec_ciks": list({r["cik"] for r in sec_recs}),
            "sec_eins": list({r["ein"] for r in sec_recs if r.get("ein")}),
            "sec_tickers": list({t for r in sec_recs for t in r.get("tickers", [])}),
            "sec_sics": list({r["sic"] for r in sec_recs}),
            "fcc_original_names": list({r["licensee_name"] for r in fcc_recs}),
            "fcc_frns": list({frn for r in fcc_recs for frn in r.get("frns", [])}),
            "fcc_facility_count_total": sum(r.get("facility_count", 0) for r in fcc_recs),
            "fcc_record_count": len(fcc_recs),
        })
    return enriched


def main():
    print("Loading candidate files...")
    with open(SEC_FILE) as f:
        sec_raw = json.load(f)
    with open(FCC_FILE) as f:
        fcc_raw = json.load(f)

    print(f"SEC raw records: {len(sec_raw)}")
    print(f"FCC raw records: {len(fcc_raw)}")

    print("\nDeduplicating by normalized name...")
    sec_groups = dedupe_sec(sec_raw)
    fcc_groups = dedupe_fcc(fcc_raw)
    print(f"SEC unique entities: {len(sec_groups)} (from {len(sec_raw)} records)")
    print(f"FCC unique entities: {len(fcc_groups)} (from {len(fcc_raw)} records)")

    sec_names = list(sec_groups.keys())
    fcc_names = list(fcc_groups.keys())

    print(f"\nFuzzy matching {len(sec_names)} SEC × {len(fcc_names)} FCC entities...")
    matches = find_matches(sec_names, fcc_names, score_cutoff=50)
    print(f"Raw match pairs found: {len(matches)}")

    enriched = enrich_matches(matches, sec_groups, fcc_groups)

    sec_matched = {m["sec_name_normalized"] for m in matches}
    fcc_matched = {m["fcc_name_normalized"] for m in matches}
    sec_only = set(sec_names) - sec_matched
    fcc_only = set(fcc_names) - fcc_matched

    tier_counts = defaultdict(int)
    for m in matches:
        tier_counts[m["tier"]] += 1

    summary = {
        "dedupe": {
            "sec_raw": len(sec_raw),
            "sec_unique": len(sec_groups),
            "sec_compaction": round(1 - len(sec_groups) / len(sec_raw), 4),
            "fcc_raw": len(fcc_raw),
            "fcc_unique": len(fcc_groups),
            "fcc_compaction": round(1 - len(fcc_groups) / len(fcc_raw), 4),
        },
        "matches": {
            "total_pairs": len(matches),
            "sec_entities_matched": len(sec_matched),
            "fcc_entities_matched": len(fcc_matched),
            "sec_only": len(sec_only),
            "fcc_only": len(fcc_only),
            "by_tier": dict(tier_counts),
        },
        "overlap_rates": {
            "sec_match_rate": round(len(sec_matched) / len(sec_names), 4) if sec_names else 0,
            "fcc_match_rate": round(len(fcc_matched) / len(fcc_names), 4) if fcc_names else 0,
        },
    }

    print("\n=== SUMMARY ===")
    print(f"\nDedupe:")
    print(f"  SEC: {summary['dedupe']['sec_raw']} → {summary['dedupe']['sec_unique']} "
          f"({summary['dedupe']['sec_compaction']:.1%} compaction)")
    print(f"  FCC: {summary['dedupe']['fcc_raw']} → {summary['dedupe']['fcc_unique']} "
          f"({summary['dedupe']['fcc_compaction']:.1%} compaction)")
    print(f"\nMatches:")
    print(f"  Total pairs: {summary['matches']['total_pairs']}")
    print(f"  High (≥90):  {tier_counts.get('high', 0)}")
    print(f"  Medium (70-89): {tier_counts.get('medium', 0)}")
    print(f"  Low (50-69): {tier_counts.get('low', 0)}")
    print(f"\nOverlap:")
    print(f"  SEC entities with FCC match: {len(sec_matched)}/{len(sec_names)} "
          f"({summary['overlap_rates']['sec_match_rate']:.1%})")
    print(f"  FCC entities with SEC match: {len(fcc_matched)}/{len(fcc_names)} "
          f"({summary['overlap_rates']['fcc_match_rate']:.1%})")
    print(f"  SEC-only (no FCC presence): {len(sec_only)}")
    print(f"  FCC-only (no SEC presence): {len(fcc_only)}")

    print(f"\nTop 20 matches:")
    for m in enriched[:20]:
        print(f"  {m['score']:5.1f} [{m['tier']:6s}] "
              f"{m['sec_original_names'][0]} ↔ {m['fcc_original_names'][0]}")

    print(f"\nSaving {len(enriched)} matches to {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(enriched, f, indent=2)

    print(f"Saving summary to {SUMMARY_FILE}")
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2)

    print("\nDone.")


if __name__ == "__main__":
    main()
