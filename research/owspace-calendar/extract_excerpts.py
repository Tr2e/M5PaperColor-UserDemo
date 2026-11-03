#!/usr/bin/env python3
"""Backfill the quotation excerpt for visually verified metadata samples.

Scope is intentionally narrow: only dates already listed in verified_samples.json
get an `excerpt` field. Each month is committed separately so Git history stays
month-keyed, matching the existing convention. Standard metadata (title/author/
source) is left untouched; this script only adds the `excerpt` field.
"""
import argparse
import json
import subprocess
import tempfile
import concurrent.futures
from pathlib import Path

from index_calendar import ROOT, BRANCH, fetch, git


def extract_one(date, url):
    status, body, _, _, error = fetch(url, 0.25)
    if status != 200 or body is None:
        return {"status": "request_error", "http_status": status, "error": error}
    try:
        with tempfile.NamedTemporaryFile(prefix="owspace-excerpt-", suffix=".jpg", delete=False) as tmp:
            tmp.write(body)
            path = tmp.name
        # A fresh subprocess per call avoids long-running pipe-staleness that
        # silently drains later months in a reused worker thread.
        proc = subprocess.Popen(["/tmp/owspace-research/ocr_metadata"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, bufsize=1)
        proc.stdin.write(json.dumps({"path": path, "year": int(date[:4])}) + "\n")
        proc.stdin.flush()
        raw = proc.stdout.readline()
        proc.stdin.close()
        proc.wait(timeout=15)
        ocr = json.loads(raw) if raw else {"excerptLines": []}
    finally:
        Path(path).unlink(missing_ok=True)
    if "error" in ocr:
        return {"status": "ocr_error", "error": ocr["error"]}
    lines = ocr.get("excerptLines", [])
    # Same normalization as index_calendar.parse_metadata: drop source-title /
    # icon lines, then collapse near-coincident Vision duplicate boxes.
    import re as _re
    from index_calendar import SOURCE_RE
    body = [l for l in lines
            if not SOURCE_RE.search(l["text"]) and not _re.search(r"[®©@™℠]", l["text"])]
    body.sort(key=lambda l: l["y"])
    dedup = []
    for l in body:
        if dedup and abs(l["y"] - dedup[-1]["y"]) < 0.017:
            if l["confidence"] > dedup[-1]["confidence"]:
                dedup[-1] = l
            continue
        dedup.append(l)
    seen_han = any(_re.search(r"[\u4e00-\u9fff]", l["text"]) for l in dedup)
    text = "".join(l["text"] for l in dedup)
    if seen_han:
        text = text.replace(" ", "")
    excerpt = text.strip() or None
    return {"status": "indexed", "excerpt": excerpt,
            "excerpt_ocr_confidence_min": min((l["confidence"] for l in lines), default=None)}


def run(args):
    if args.commit and git("branch", "--show-current") != BRANCH:
        raise SystemExit("Unexpected branch")
    verified = json.loads((ROOT / "verified_samples.json").read_text())
    # Group verified dates by month.
    by_month = {}
    for date in verified:
        by_month.setdefault(date[:7], []).append(date)

    for month in sorted(by_month):
        path = ROOT / "months" / f"{month}.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        targets = {d: r for d in by_month[month] for r in rows if r["date"] == d and r["status"] == "indexed"}
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(extract_one, d, r["url"]): d for d, r in targets.items()}
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
            if row.get("excerpt") != res["excerpt"]:
                row["excerpt"] = res["excerpt"]
                row["excerpt_ocr_confidence_min"] = res["excerpt_ocr_confidence_min"]
                changed += 1
        if changed:
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            print(f"{path.stem}: {changed} excerpt(s) written", flush=True)
            if args.commit:
                rel = str(path.relative_to(ROOT))
                git("add", "--", rel)
                if git("diff", "--cached", "--name-only", "--", rel):
                    git("commit", "--only", "-m",
                        f"data(owspace): add verified-sample excerpts in {path.stem}", "--", rel)
        else:
            print(f"{path.stem}: no changes", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--interval", type=float, default=0.25)
    p.add_argument("--commit", action="store_true")
    run(p.parse_args())
