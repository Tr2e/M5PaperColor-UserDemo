#!/usr/bin/env python3
"""Backfill the author's foreign-language name for every readable date.

The existing metadata pipeline already located attribution lines but discarded
the foreign spelling (Latin script) once the Chinese name was resolved. This
script re-runs OCR + parse_metadata for every indexed date and writes the new
``author_foreign_name`` field, leaving title/author/source untouched. Each month
is committed separately so Git history stays month-keyed. Idempotent: dates that
already carry ``author_foreign_name`` are skipped.
"""
import argparse
import json
import subprocess
import tempfile
import concurrent.futures
from pathlib import Path

from index_calendar import ROOT, BRANCH, fetch, git, parse_metadata


def analyze_one(date, url):
    status, body, _, _, error = fetch(url, 0.25)
    if status != 200 or body is None:
        return {"status": "request_error", "http_status": status, "error": error}
    try:
        with tempfile.NamedTemporaryFile(prefix="owspace-name-", suffix=".jpg", delete=False) as tmp:
            tmp.write(body)
            path = tmp.name
        proc = subprocess.Popen(["/tmp/owspace-research/ocr_metadata"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, bufsize=1)
        proc.stdin.write(json.dumps({"path": path, "year": int(date[:4])}) + "\n")
        proc.stdin.flush()
        raw = proc.stdout.readline()
        proc.stdin.close()
        proc.wait(timeout=15)
        ocr = json.loads(raw) if raw else {}
    finally:
        Path(path).unlink(missing_ok=True)
    if "error" in ocr:
        return {"status": "ocr_error", "error": ocr["error"]}
    meta = parse_metadata(ocr)
    return {
        "status": "indexed",
        "author_foreign_name": meta["author_foreign_name"],
        "author_roles": meta["author_roles"],
    }


def run(args):
    if args.commit and git("branch", "--show-current") != BRANCH:
        raise SystemExit("Unexpected branch")
    by_month = {}
    for path in sorted((ROOT / "months").glob("*-*.jsonl")):
        month = path.stem
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        targets = [r for r in rows if r["status"] == "indexed"
                   and not r.get("author_foreign_name")]
        if targets:
            by_month[month] = targets

    for month in sorted(by_month):
        path = ROOT / "months" / f"{month}.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        targets = {r["date"]: r for r in by_month[month]}
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(analyze_one, d, r["url"]): d for d, r in targets.items()}
            for future in concurrent.futures.as_completed(futures):
                d = futures[future]
                results[d] = future.result()
        changed = 0
        for row in rows:
            if row["date"] not in results:
                continue
            res = results[row["date"]]
            if res["status"] != "indexed":
                continue
            new_fn = res["author_foreign_name"]
            if row.get("author_foreign_name") != new_fn:
                if new_fn:
                    row["author_foreign_name"] = new_fn
                    changed += 1
            # Also fill a missing role when the same OCR pass resolved one.
            if not row.get("author_roles") and res["author_roles"]:
                row["author_roles"] = res["author_roles"]
                changed += 1
        if changed:
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            print(f"{path.stem}: {changed} record(s) updated", flush=True)
            if args.commit:
                rel = str(path.relative_to(ROOT))
                git("add", "--", rel)
                if git("diff", "--cached", "--name-only", "--", rel):
                    git("commit", "--only", "-m",
                        f"data(owspace): add author foreign names in {path.stem}", "--", rel)
        else:
            print(f"{path.stem}: no changes", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--interval", type=float, default=0.25)
    p.add_argument("--commit", action="store_true")
    run(p.parse_args())
