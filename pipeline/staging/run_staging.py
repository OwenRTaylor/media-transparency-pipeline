"""Layer 3 entry point — stage -> validate -> export a list[ExtractorResult].

Run against the synthetic Fox fixture:
    python3 -m pipeline.staging.run_staging

Real extractor output lands async from other sessions; swap `fox_result()` for
the collected ExtractorResults once they exist. Nothing here is source-specific.

INV-11: a validation ERROR does not drop rows. Offenders are written to
data/staging/manual_review.json and export is refused (fail-loud), so a corrupt
graph never silently reaches the SQLite artifact. WARNING/SKIPPED never block.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import List

from pipeline.contracts import ExtractorResult
from pipeline.staging import export as export_mod
from pipeline.staging import stage as stage_mod
from pipeline.staging import validate as validate_mod
from pipeline.staging.fixtures import fox_result

DATA_DIR = "data/staging"                       # gitignored (CLAUDE.md)
SQLITE_PATH = os.path.join(DATA_DIR, "media_transparency.sqlite")
REVIEW_PATH = os.path.join(DATA_DIR, "manual_review.json")


def run(results: List[ExtractorResult], sqlite_path: str = SQLITE_PATH) -> int:
    os.makedirs(DATA_DIR, exist_ok=True)

    con = stage_mod.stage(results)
    report = validate_mod.validate(con)

    for v in report.violations:
        marker = {"ERROR": "✗", "WARNING": "!", "SKIPPED": "–"}.get(v.severity, "?")
        print(f"  [{marker}] {v.severity:<8} {v.rule}: {v.detail}")

    if not report.ok:
        with open(REVIEW_PATH, "w") as f:
            json.dump([asdict(v) for v in report.errors], f, indent=2)
        print(f"\nExport REFUSED — {len(report.errors)} error(s) flagged for review "
              f"-> {REVIEW_PATH} (no rows dropped, INV-11)")
        return 1

    counts = export_mod.export(con, sqlite_path)
    print(f"\nExported -> {sqlite_path}")
    for table, n in counts.items():
        print(f"    {table:<22} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run([fox_result()]))
