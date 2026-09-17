"""D1: Scan SEC bulk submissions for media companies by SIC code.

Reads the SEC bulk submissions directory (one JSON file per CIK),
filters by core media SIC codes, and outputs a candidate list.

Input:  unfiltered_data/submissions/ (272K JSON files from SEC EDGAR bulk download)
Output: list of MediaCandidate dicts, one per matching CIK
"""

import json
import os
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CORE_MEDIA_SICS: dict[str, str] = {
    "2711": "Newspapers",
    "2721": "Periodicals",
    "2731": "Books",
    "2741": "Miscellaneous Publishing",
    "4832": "Radio Broadcasting",
    "4833": "Television Broadcasting",
    "4841": "Cable & Pay TV",
    "7812": "Motion Picture Production",
    "7819": "Allied to Motion Picture Production",
    "7822": "Motion Picture Distribution",
    "7829": "Allied to Motion Picture Distribution",
    "7830": "Motion Picture Theaters",
}

BORDERLINE_SICS: dict[str, str] = {
    "4812": "Radiotelephone Communications",
    "4813": "Telephone Communications",
    "4899": "Communications Services NEC",
    "3663": "Radio & TV Equipment",
    "7372": "Prepackaged Software",
}


@dataclass
class MediaCandidate:
    cik: str
    name: str
    sic: str
    sic_description: str
    source: str = "sec_sic_scan"
    tickers: list[str] = field(default_factory=list)
    ein: Optional[str] = None
    entity_type: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    state_of_incorporation: Optional[str] = None
    former_names: list[str] = field(default_factory=list)


def scan_submissions(
    submissions_dir: str | Path,
    sic_filter: dict[str, str] | None = None,
    include_borderline: bool = False,
) -> list[MediaCandidate]:
    """Scan SEC submissions directory for media companies.

    Args:
        submissions_dir: Path to bulk submissions directory.
        sic_filter: SIC codes to match. Defaults to CORE_MEDIA_SICS.
        include_borderline: If True, also include BORDERLINE_SICS.

    Returns:
        List of MediaCandidate objects, one per matching CIK.
    """
    if sic_filter is None:
        sic_filter = dict(CORE_MEDIA_SICS)
        if include_borderline:
            sic_filter.update(BORDERLINE_SICS)

    submissions_dir = Path(submissions_dir)
    candidates: list[MediaCandidate] = []
    errors = 0
    scanned = 0

    for fname in os.listdir(submissions_dir):
        if not fname.endswith(".json"):
            continue
        scanned += 1
        try:
            with open(submissions_dir / fname) as f:
                data = json.load(f)

            sic = data.get("sic", "")
            if sic not in sic_filter:
                continue

            former = data.get("formerNames", [])
            former_names = [fn.get("name", "") for fn in former if fn.get("name")]

            candidates.append(
                MediaCandidate(
                    cik=str(data.get("cik", "")).lstrip("0") or data.get("cik", ""),
                    name=data.get("name", ""),
                    sic=sic,
                    sic_description=data.get("sicDescription", sic_filter.get(sic, "")),
                    tickers=data.get("tickers", []),
                    ein=data.get("ein"),
                    entity_type=data.get("entityType"),
                    website=data.get("website", ""),
                    category=data.get("category", ""),
                    state_of_incorporation=data.get("stateOfIncorporation", ""),
                    former_names=former_names,
                )
            )
        except Exception as e:
            errors += 1
            logger.warning("Failed to parse %s: %s", fname, e)

    logger.info(
        "Scanned %d submissions, found %d media candidates, %d errors",
        scanned, len(candidates), errors,
    )
    return candidates


def save_candidates(candidates: list[MediaCandidate], output_path: str | Path) -> None:
    """Write candidates to JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump([asdict(c) for c in candidates], f, indent=2)
    logger.info("Wrote %d candidates to %s", len(candidates), output_path)


def summarize(candidates: list[MediaCandidate]) -> dict:
    """Quick stats on candidate list."""
    from collections import Counter

    sic_counts = Counter(f"{c.sic} - {c.sic_description}" for c in candidates)
    with_tickers = sum(1 for c in candidates if c.tickers)
    with_ein = sum(1 for c in candidates if c.ein)
    with_website = sum(1 for c in candidates if c.website)

    return {
        "total": len(candidates),
        "with_tickers": with_tickers,
        "with_ein": with_ein,
        "with_website": with_website,
        "by_sic": dict(sic_counts.most_common()),
    }


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    submissions_dir = sys.argv[1] if len(sys.argv) > 1 else "unfiltered_data/submissions"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/discovery/sec_media_candidates.json"
    include_borderline = "--borderline" in sys.argv

    candidates = scan_submissions(submissions_dir, include_borderline=include_borderline)
    save_candidates(candidates, output_path)

    stats = summarize(candidates)
    print(f"\nTotal candidates: {stats['total']}")
    print(f"  With tickers: {stats['with_tickers']}")
    print(f"  With EIN: {stats['with_ein']}")
    print(f"  With website: {stats['with_website']}")
    print(f"\nBy SIC:")
    for sic_desc, count in sorted(stats["by_sic"].items(), key=lambda x: -x[1]):
        print(f"  {sic_desc}: {count}")
