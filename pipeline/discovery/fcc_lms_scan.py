"""D2: Scan FCC LMS dump for broadcast media entities.

Extracts licensee entities from the LMS bulk dump. Uses two tables:
- application_facility.dat: licensee_name + facility_id + facility_type (simpler path)
- app_party.dat: FRN + legal_party_name + application_id (enrichment for FRN)

Input:  unfiltered_data/Current_LMS_Dump/
Output: list of FccCandidate dicts, one per unique licensee entity
"""

import csv
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json

logger = logging.getLogger(__name__)

BROADCAST_SERVICE_CODES = {
    "AM", "FM", "FL", "FX",      # radio
    "TV", "DTV", "DCA",          # full-power TV
    "LPA", "LPD", "LPT", "LPX", # low-power TV
    "323", "323E",               # translators/boosters (Class A)
    "FA", "FB", "FR",            # auxiliary
}


@dataclass
class FccCandidate:
    licensee_name: str
    source: str = "fcc_lms_scan"
    facility_count: int = 0
    facility_ids: list[str] = field(default_factory=list)
    service_codes: list[str] = field(default_factory=list)
    frns: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    dba_names: list[str] = field(default_factory=list)


def scan_application_facility(
    lms_dir: str | Path,
    active_only: bool = True,
) -> dict[str, FccCandidate]:
    """Extract unique licensee entities from application_facility.dat.

    Returns dict keyed by normalized licensee name.
    """
    lms_dir = Path(lms_dir)
    af_path = lms_dir / "application_facility.dat"

    candidates: dict[str, FccCandidate] = {}
    app_to_licensee: dict[str, str] = {}
    rows_read = 0

    with open(af_path, "r") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            rows_read += 1
            if active_only and (row.get("active_ind") or "").strip() != "Y":
                continue

            name = (row.get("licensee_name") or "").strip()
            if not name:
                continue

            fac_id = (row.get("afac_facility_id") or "").strip()
            app_id = (row.get("afac_application_id") or "").strip()
            community_state = (row.get("afac_community_state_code") or "").strip()

            key = name.upper()

            if key not in candidates:
                candidates[key] = FccCandidate(licensee_name=name)

            c = candidates[key]
            c.facility_count += 1

            if fac_id and fac_id not in c.facility_ids:
                c.facility_ids.append(fac_id)

            if community_state and community_state not in c.states:
                c.states.append(community_state)

            if app_id:
                app_to_licensee[app_id] = key

    logger.info(
        "Read %d rows from application_facility.dat, found %d unique licensees",
        rows_read, len(candidates),
    )
    return candidates, app_to_licensee


def enrich_with_frn(
    candidates: dict[str, FccCandidate],
    app_to_licensee: dict[str, str],
    lms_dir: str | Path,
) -> None:
    """Add FRN from app_party.dat by joining on application_id."""
    lms_dir = Path(lms_dir)
    party_path = lms_dir / "app_party.dat"

    matched = 0
    with open(party_path, "r") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            app_id = (row.get("apar_aapp_application_id") or "").strip()
            if app_id not in app_to_licensee:
                continue

            frn = (row.get("apar_frn") or "").strip()
            dba = (row.get("apar_dba_name") or "").strip()
            key = app_to_licensee[app_id]

            if key not in candidates:
                continue

            c = candidates[key]
            if frn and frn not in c.frns:
                c.frns.append(frn)
                matched += 1

            if dba and dba not in c.dba_names:
                c.dba_names.append(dba)

    logger.info("Enriched %d FRN matches from app_party.dat", matched)


def scan_party_entities(
    lms_dir: str | Path,
    existing_keys: set[str] | None = None,
) -> list[FccCandidate]:
    """Extract entities from app_party.dat that aren't in application_facility.

    Catches radio companies filing under DBA names (Salem, Cumulus, iHeart, etc.)
    that don't appear as licensee_name in application_facility.dat.
    """
    lms_dir = Path(lms_dir)
    party_path = lms_dir / "app_party.dat"
    existing_keys = existing_keys or set()

    entities: dict[str, FccCandidate] = {}
    rows_read = 0

    with open(party_path, "r") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            rows_read += 1
            legal_name = (row.get("apar_legal_party_name") or "").strip()
            dba = (row.get("apar_dba_name") or "").strip()
            frn = (row.get("apar_frn") or "").strip()

            name = legal_name or dba
            if not name:
                continue

            key = name.upper()
            if key in existing_keys:
                continue

            if key not in entities:
                entities[key] = FccCandidate(licensee_name=name)

            c = entities[key]
            c.facility_count += 1

            if frn and frn not in c.frns:
                c.frns.append(frn)

            if dba and dba not in c.dba_names and dba != name:
                c.dba_names.append(dba)

    logger.info(
        "Read %d rows from app_party.dat, found %d additional entities",
        rows_read, len(entities),
    )
    return list(entities.values())


def scan_lms(
    lms_dir: str | Path,
    enrich_frn: bool = True,
    min_facilities: int = 0,
) -> list[FccCandidate]:
    """Full LMS scan: extract licensees, optionally enrich with FRN.

    Args:
        lms_dir: Path to Current_LMS_Dump directory.
        enrich_frn: If True, join app_party.dat for FRN data.
        min_facilities: Only return candidates with at least this many facilities.

    Returns:
        List of FccCandidate objects sorted by facility count descending.
    """
    candidates, app_to_licensee = scan_application_facility(lms_dir)

    if enrich_frn:
        enrich_with_frn(candidates, app_to_licensee, lms_dir)

    party_only = scan_party_entities(lms_dir, existing_keys=set(candidates.keys()))
    for pc in party_only:
        key = pc.licensee_name.upper()
        candidates[key] = pc

    result = list(candidates.values())
    if min_facilities > 0:
        result = [c for c in result if c.facility_count >= min_facilities]

    result.sort(key=lambda c: c.facility_count, reverse=True)

    logger.info("Returning %d FCC candidates (min_facilities=%d)", len(result), min_facilities)
    return result


def save_candidates(candidates: list[FccCandidate], output_path: str | Path) -> None:
    """Write candidates to JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump([asdict(c) for c in candidates], f, indent=2)
    logger.info("Wrote %d candidates to %s", len(candidates), output_path)


def summarize(candidates: list[FccCandidate]) -> dict:
    """Quick stats on candidate list."""
    with_frn = sum(1 for c in candidates if c.frns)
    total_facilities = sum(c.facility_count for c in candidates)
    multi_state = sum(1 for c in candidates if len(c.states) > 1)

    return {
        "total_licensees": len(candidates),
        "total_facilities": total_facilities,
        "with_frn": with_frn,
        "multi_state": multi_state,
        "top_20": [
            {"name": c.licensee_name, "facilities": c.facility_count, "frns": len(c.frns), "states": len(c.states)}
            for c in candidates[:20]
        ],
    }


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    lms_dir = sys.argv[1] if len(sys.argv) > 1 else "unfiltered_data/Current_LMS_Dump"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/discovery/fcc_media_candidates.json"
    skip_frn = "--skip-frn" in sys.argv

    candidates = scan_lms(lms_dir, enrich_frn=not skip_frn)
    save_candidates(candidates, output_path)

    stats = summarize(candidates)
    print(f"\nTotal licensees: {stats['total_licensees']}")
    print(f"Total facilities: {stats['total_facilities']}")
    print(f"  With FRN: {stats['with_frn']}")
    print(f"  Multi-state: {stats['multi_state']}")
    print(f"\nTop 20 by facility count:")
    for entry in stats["top_20"]:
        print(f"  {entry['name'][:50]:50s}  fac: {entry['facilities']:5d}  frns: {entry['frns']}  states: {entry['states']}")
