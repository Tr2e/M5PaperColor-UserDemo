#!/usr/bin/env python3
"""Extract PaperColor DisplayMetrics records from serial logs.

The script is intentionally standard-library-only so the same captured log can
be processed on a development machine or in CI.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, TextIO


FIELDS = (
    "source",
    "success",
    "total_us",
    "render_us",
    "render_to_refresh_us",
    "panel_us",
    "internal_before",
    "internal_after",
    "internal_largest",
    "psram_before",
    "psram_after",
    "psram_largest",
)

METRIC_PATTERN = re.compile(
    r"DisplayMetrics:\s+"
    r"source=(?P<source>\S+)\s+"
    r"success=(?P<success>[01])\s+"
    r"total_us=(?P<total_us>\d+)\s+"
    r"render_us=(?P<render_us>\d+)\s+"
    r"render_to_refresh_us=(?P<render_to_refresh_us>\d+)\s+"
    r"panel_us=(?P<panel_us>\d+)\s+"
    r"internal_before=(?P<internal_before>\d+)\s+"
    r"internal_after=(?P<internal_after>\d+)\s+"
    r"internal_largest=(?P<internal_largest>\d+)\s+"
    r"psram_before=(?P<psram_before>\d+)\s+"
    r"psram_after=(?P<psram_after>\d+)\s+"
    r"psram_largest=(?P<psram_largest>\d+)"
)

PIPELINE_PATTERN = re.compile(
    r"PaperColorPipeline:\s+"
    r"mode=(?P<mode>\S+)\s+"
    r"prepare_us=(?P<prepare_us>\d+)\s+"
    r"workspace_bytes=(?P<workspace_bytes>\d+)"
)


def parse_lines(lines: Iterable[str]) -> list[dict[str, int | str]]:
    records: list[dict[str, int | str]] = []
    for line in lines:
        match = METRIC_PATTERN.search(line)
        if not match:
            continue
        record: dict[str, int | str] = {"source": match.group("source")}
        for field in FIELDS[1:]:
            record[field] = int(match.group(field))
        records.append(record)
    return records


def parse_pipeline(lines: Iterable[str]) -> dict[str, int | str] | None:
    latest: dict[str, int | str] | None = None
    for line in lines:
        match = PIPELINE_PATTERN.search(line)
        if match:
            latest = {
                "mode": match.group("mode"),
                "prepare_us": int(match.group("prepare_us")),
                "workspace_bytes": int(match.group("workspace_bytes")),
            }
    return latest


def percentile(values: list[int], percent: float) -> int:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    rank = max(0, math.ceil(percent * len(ordered)) - 1)
    return ordered[rank]


def summarize(records: list[dict[str, int | str]]) -> dict[str, object]:
    grouped: dict[str, list[dict[str, int | str]]] = defaultdict(list)
    for record in records:
        grouped[str(record["source"])].append(record)

    sources: dict[str, object] = {}
    for source, items in sorted(grouped.items()):
        successful = [item for item in items if item["success"] == 1]
        total_values = [int(item["total_us"]) for item in successful]
        panel_values = [int(item["panel_us"]) for item in successful]
        sources[source] = {
            "count": len(items),
            "success_count": len(successful),
            "failure_count": len(items) - len(successful),
            "total_us_p50": percentile(total_values, 0.50) if total_values else None,
            "total_us_p95": percentile(total_values, 0.95) if total_values else None,
            "panel_us_p50": percentile(panel_values, 0.50) if panel_values else None,
            "panel_us_p95": percentile(panel_values, 0.95) if panel_values else None,
            "min_internal_after": min((int(item["internal_after"]) for item in items), default=None),
            "min_psram_after": min((int(item["psram_after"]) for item in items), default=None),
        }

    return {"schema_version": 1, "record_count": len(records), "sources": sources}


def iter_inputs(paths: list[Path]) -> Iterable[str]:
    if not paths:
        yield from sys.stdin
        return
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            yield from handle


def write_csv(records: list[dict[str, int | str]], handle: TextIO) -> None:
    writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="*", type=Path, help="serial log files; stdin is used when omitted")
    parser.add_argument("--csv", type=Path, help="write extracted records to this CSV path")
    parser.add_argument("--summary", type=Path, help="write per-source summary JSON to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = parse_lines(iter_inputs(args.logs))
    if not records:
        print("No DisplayMetrics records found", file=sys.stderr)
        return 1

    if args.csv:
        with args.csv.open("w", encoding="utf-8", newline="") as handle:
            write_csv(records, handle)
    else:
        write_csv(records, sys.stdout)

    summary = summarize(records)
    if args.summary:
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
