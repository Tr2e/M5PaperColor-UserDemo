#!/usr/bin/env python3
"""Validate date coverage and summarize an annual machine-generated index."""
import argparse
import calendar
from collections import Counter, defaultdict
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def review(year):
    rows = []
    for month in range(1, 13):
        path = ROOT / "months" / f"{year}-{month:02d}.jsonl"
        batch = [json.loads(line) for line in path.read_text().splitlines()]
        actual = [r["date"] for r in batch]
        expected = [f"{year}-{month:02d}-{day:02d}" for day in range(1, calendar.monthrange(year, month)[1] + 1)]
        assert actual == expected, f"Incomplete/duplicate/out-of-order month: {path}"
        for row in batch:
            assert row.get("quotation_status") == "not_collected"
            assert not any(key in row for key in ("quote", "quotation", "text", "body", "ocr_text"))
        rows.extend(batch)
    indexed = [r for r in rows if r["status"] == "indexed"]
    hashes = defaultdict(list)
    for row in indexed:
        hashes[row["image_sha256"]].append(row["date"])
    result = {
        "year": year,
        "reviewed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "date_coverage_pass": True,
        "expected_days": 366 if calendar.isleap(year) else 365,
        "record_count": len(rows),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "first_available": indexed[0]["date"] if indexed else None,
        "last_available": indexed[-1]["date"] if indexed else None,
        "field_counts": {field: sum(bool(r.get(field)) for r in indexed) for field in ["title", "source", "author"]},
        "visually_verified_samples": sum(r.get("review_status") == "sample_metadata_verified" for r in indexed),
        "title_kind_counts": dict(Counter(r.get("title_kind") for r in indexed)),
        "review_flag_counts": dict(Counter(flag for r in indexed for flag in r.get("review_flags", []))),
        "missing_dates": [r["date"] for r in rows if r["status"] == "missing_at_tested_url"],
        "error_dates": [r["date"] for r in rows if r["status"] not in ("indexed", "missing_at_tested_url")],
        "identical_image_groups": [dates for dates in hashes.values() if len(dates) > 1],
        "image_date_mismatches": [{"requested_date": r['date'], "printed_date": r['printed_date']} for r in indexed if r.get('date_verification')=='visually_checked_mismatch'],
        "top_authors_machine_extracted": Counter(r["author"] for r in indexed if r.get("author")).most_common(12),
        "top_sources_machine_extracted": Counter(r["source"] for r in indexed if r.get("source")).most_common(12),
        "assessment": "日期覆盖检查完成；字段为机器提取，未经逐条人工核验。完整性检查不代表OCR准确率。"
    }
    output = ROOT / "years" / f"{year}-review.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("missing_dates", "top_authors_machine_extracted", "top_sources_machine_extracted")}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("year", type=int)
    review(p.parse_args().year)
