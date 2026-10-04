"""Layer 3 — post-stage validation. Fail -> flag for manual review, not silent drop.

Implements the data-model.md "Invariants (enforced via validation)" list against
the DuckDB staging tables. Per INV-11 nothing is deleted: every check appends a
`Violation` to the report; the caller (run_staging.py) writes offenders to a
manual-review file and refuses to export a corrupt graph rather than dropping rows.

Severity:
  ERROR   — graph-corrupting; blocks export.
  WARNING — data-quality signal; recorded, does not block.

Checks needing external inputs not wired in v1 staging (domain_map.json,
seed_map.json) and cross-run checks (concentration sanity, diff report) are
reported as SKIPPED so their absence is visible, not silently missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List
from urllib.parse import urlparse

import duckdb

# Active relationships older than this are stale (data-model.md). WARNING, not fatal.
STALE_MONTHS = 36


@dataclass
class Violation:
    rule: str
    severity: str          # ERROR | WARNING | SKIPPED
    detail: str
    offenders: List[str] = field(default_factory=list)  # natural keys, for triage


@dataclass
class ValidationReport:
    violations: List[Violation] = field(default_factory=list)

    @property
    def errors(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == "ERROR"]

    @property
    def ok(self) -> bool:
        """True when no ERROR-severity violation was found (WARNING/SKIPPED ok)."""
        return not self.errors

    def add(self, rule: str, severity: str, detail: str,
            offenders: List[str] | None = None) -> None:
        self.violations.append(Violation(rule, severity, detail, offenders or []))


def _keys(con: duckdb.DuckDBPyConnection, sql: str) -> List[str]:
    return [str(row[0]) for row in con.execute(sql).fetchall()]


def validate(con: duckdb.DuckDBPyConnection,
             today: date | None = None) -> ValidationReport:
    """Run every enforced invariant over staging. Returns a report; drops nothing."""
    today = today or date.today()
    r = ValidationReport()

    # 1. Every entity: canonical_name not NULL / empty.
    bad = _keys(con, "SELECT entity_key FROM stg_entities "
                     "WHERE canonical_name IS NULL OR trim(canonical_name) = ''")
    if bad:
        r.add("entity.canonical_name_not_empty", "ERROR",
              f"{len(bad)} entities with empty canonical_name", bad)

    # 2. Every relationship: confidence not NULL (INV-9).
    bad = _keys(con, "SELECT rel_key FROM stg_relationships WHERE confidence IS NULL")
    if bad:
        r.add("relationship.confidence_not_null", "ERROR",
              f"{len(bad)} relationships with NULL confidence", bad)

    # 3. Every relationship: >=1 provenance record (INV-3).
    bad = _keys(con,
                "SELECT rel_key FROM stg_relationships r WHERE NOT EXISTS ("
                "  SELECT 1 FROM stg_provenance p "
                "  WHERE p.target_type = 'relationship' AND p.target_id = r.rel_key)")
    if bad:
        r.add("relationship.has_provenance", "ERROR",
              f"{len(bad)} relationships with no provenance record", bad)

    # 4. No orphan relationships (source + target must exist).
    bad = _keys(con,
                "SELECT rel_key FROM stg_relationships r WHERE "
                "  source_entity_id NOT IN (SELECT entity_key FROM stg_entities) "
                "  OR target_entity_id NOT IN (SELECT entity_key FROM stg_entities)")
    if bad:
        r.add("relationship.no_orphan", "ERROR",
              f"{len(bad)} relationships reference a missing entity", bad)

    # 5. No self-referential relationship.
    bad = _keys(con, "SELECT rel_key FROM stg_relationships "
                     "WHERE source_entity_id = target_entity_id")
    if bad:
        r.add("relationship.no_self_reference", "ERROR",
              f"{len(bad)} self-referential relationships", bad)

    # 6. No duplicates (same source + target + type).
    bad = _keys(con,
                "SELECT source_entity_id || '|' || target_entity_id || '|' || type "
                "FROM stg_relationships "
                "GROUP BY source_entity_id, target_entity_id, type HAVING count(*) > 1")
    if bad:
        r.add("relationship.no_duplicate", "ERROR",
              f"{len(bad)} duplicated (source,target,type) relationships", bad)

    # 7a. last_verified not future-dated (ERROR).
    bad = [str(row[0]) for row in con.execute(
        "SELECT rel_key FROM stg_relationships WHERE last_verified > ?",
        [today]).fetchall()]
    if bad:
        r.add("relationship.last_verified_not_future", "ERROR",
              f"{len(bad)} relationships with future-dated last_verified", bad)

    # 7b. Active relationship not older than STALE_MONTHS (WARNING — staleness).
    cutoff = date(today.year - STALE_MONTHS // 12,
                  today.month, min(today.day, 28))
    bad = [str(row[0]) for row in con.execute(
        "SELECT rel_key FROM stg_relationships "
        "WHERE status = 'active' AND last_verified < ?", [cutoff]).fetchall()]
    if bad:
        r.add("relationship.active_not_stale", "WARNING",
              f"{len(bad)} active relationships older than {STALE_MONTHS} months", bad)

    # 8. Every access_link URL syntactically valid (tiers A/B are URLs; C = file path).
    bad = []
    for tier, location in con.execute(
            "SELECT tier, location FROM stg_access_links WHERE tier IN ('A', 'B')"
    ).fetchall():
        parsed = urlparse(location or "")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            bad.append(location)
    if bad:
        r.add("access_link.url_valid", "ERROR",
              f"{len(bad)} tier-A/B access links are not valid URLs", bad)

    # 9. Every outlet entity: >=1 relationship (as source or target).
    bad = _keys(con,
                "SELECT entity_key FROM stg_entities e WHERE e.type = 'outlet' "
                "AND entity_key NOT IN ("
                "  SELECT source_entity_id FROM stg_relationships "
                "  UNION SELECT target_entity_id FROM stg_relationships)")
    if bad:
        r.add("outlet.has_relationship", "ERROR",
              f"{len(bad)} outlet entities with no relationship", bad)

    # 10. Every domain resolves to a valid entity (staging substitute for the
    #     domain_map->entity check; full domain_map wiring is Layer-2/config).
    bad = _keys(con,
                "SELECT domain FROM stg_domains "
                "WHERE entity_key NOT IN (SELECT entity_key FROM stg_entities)")
    if bad:
        r.add("domain.resolves_to_entity", "ERROR",
              f"{len(bad)} domains point at a missing entity", bad)

    # Checks not runnable from staging alone — surfaced, not silently dropped.
    r.add("seed_map.entities_created", "SKIPPED",
          "needs seed_map.json fixture (not wired into Layer-3 staging in v1)")
    r.add("concentration.sanity", "SKIPPED",
          "needs real FCC totals + full dataset (not applicable to fixture)")
    r.add("diff.vs_prior_run", "SKIPPED",
          "needs a prior export to diff against (cross-run concern)")

    return r
