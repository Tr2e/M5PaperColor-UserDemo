#!/usr/bin/env python3
"""Build a dated bibliographic index. Does not archive images or quotation text."""
import argparse
import calendar
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
BRANCH = "codex/owspace-calendar-index-2015-2025"
BASE = "https://img.owspace.com/Public/uploads/Download"
ROLES = ("作家", "诗人", "哲学家", "演员", "导演", "编剧", "记者", "主持人", "歌手", "乐队", "音乐人", "音乐家", "艺术家", "画家", "摄影师", "思想家", "学者", "科学家", "数学家", "物理学家", "心理学家", "社会学家", "历史学家", "文学家", "评论家", "小说家", "散文家", "剧作家", "翻译家", "编辑", "政治家", "教育家", "建筑师", "设计师", "经济学家", "人类学家", "艺术团体", "旅行家", "探险家", "舞蹈家", "运动员", "革命家", "博物学家", "法学家", "神学家", "出版人", "词人", "词作家", "曲作家", "作曲家", "喜剧演员", "脱口秀演员")
ROLE_RE = re.compile("|".join(sorted(ROLES, key=len, reverse=True)))
SOURCE_RE = re.compile(r"[《〈]([^》〉]{1,100})[》〉]")
local = threading.local()
rate_lock = threading.Lock()
last_request = 0.0
processes = []


def clean(text):
    text = text.replace("•", "·").replace("・", "·")
    text = re.sub(r"\s*·\s*", "·", text)
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s+", " ", text).strip(" ，,；;。")


def parse_metadata(ocr):
    flags = []
    titles = ocr.get("titles", [])
    title = clean(titles[0]["text"]).replace(" ", "") if len(titles) == 1 else None
    if not title:
        flags.append("title_unresolved")
    if len(titles) > 1:
        flags.append("multiple_title_candidates")
    sources = list(dict.fromkeys(clean(m.group(1)) for line in ocr.get("sources", [])
                                 for m in SOURCE_RE.finditer(line["text"])))
    rows = sorted(ocr.get("attribution", []), key=lambda x: (x["y"], x["x"]))
    groups = []
    for row in rows:
        if groups and abs(groups[-1][0]["y"] - row["y"]) < .014:
            groups[-1].append(row)
        else:
            groups.append([row])
    rows = [{"text": " ".join(r["text"] for r in sorted(g, key=lambda r: r["x"])),
             "confidence": min(r["confidence"] for r in g)} for g in groups]
    people, roles, confidence = [], [], []
    for row in rows:
        text = SOURCE_RE.sub("", row["text"])
        text = re.sub(r"[單单]向[历曆曆]|OWSPACE", "", text, flags=re.I)
        # The calibrated footer contains short bibliographic lines. Reject any
        # sentence-like or long text instead of serializing possible body text.
        if re.search(r"[。！？!?]|我们|你们|他们|她们|这是|不是|就是|没有|一个|自己|只要|因为|所以", text):
            continue
        text = clean(text)
        confidence.append(row["confidence"])
        roles.extend(ROLE_RE.findall(text))
        text = ROLE_RE.sub("", text)
        text = re.sub(r"[A-Za-z][A-Za-z\s.'’\-]*", "", text)
        text = clean(text).strip(" ，,、；;：:")
        if re.fullmatch(r"[\u3400-\u9fff]{0,5}(民谣|谚语|俗语|格言)", text):
            sources.append(text)
            continue
        if text in ("电影", "电视剧", "纪录片", "歌曲", "小说", "诗歌", "单向空间"):
            continue
        if text and len(text) <= 24:
            people.append(text)
    people = list(dict.fromkeys(people))
    if not people:
        flags.append("author_unresolved")
    if not sources:
        flags.append("source_not_detected")
    confidence += [r["confidence"] for r in titles + ocr.get("sources", [])]
    if confidence and min(confidence) < .5:
        flags.append("low_ocr_confidence")
    return {
        "title": title,
        "title_kind": title[0] if title else None,
        "source": "；".join(dict.fromkeys(sources)) or None,
        "author": "；".join(people) or None,
        "author_roles": list(dict.fromkeys(roles)),
        "ocr_confidence_min": min(confidence) if confidence else None,
        "review_flags": list(dict.fromkeys(flags)),
        "review_status": "machine_extracted_not_human_verified",
        "quotation_status": "not_collected",
    }


def fetch(url, interval):
    global last_request
    for attempt in range(3):
        with rate_lock:
            time.sleep(max(0, interval - (time.monotonic() - last_request)))
            last_request = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OWSpaceMetadataResearch/1.0"})
            with urllib.request.urlopen(req, timeout=25) as response:
                body = response.read(6_000_001)
                return response.status, body, response.headers.get("Content-Type", ""), response.headers.get("Last-Modified"), None
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                return exc.code, None, None, None, None
            if attempt == 2:
                return exc.code, None, None, None, str(exc)
            time.sleep(2 ** (attempt + 1))
        except Exception as exc:
            if attempt == 2:
                return None, None, None, None, str(exc)
            time.sleep(2 ** (attempt + 1))


def one(date, args):
    url = f"{BASE}/{date.year}/{date:%m%d}.jpg"
    record = {"date": str(date), "url": url, "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    status, body, content_type, modified, error = fetch(url, args.interval)
    record.update(http_status=status, content_type=content_type)
    if body is None:
        record.update(status="missing_at_tested_url" if status in (404, 410) else "request_error", error=error,
                      title=None, source=None, author=None, quotation_status="not_collected")
        return record
    image_format = "jpeg" if body.startswith(b"\xff\xd8") else "png" if body.startswith(b"\x89PNG\r\n\x1a\n") else None
    if not image_format or len(body) > 6_000_000:
        record.update(status="unexpected_response", error="Expected a JPEG or PNG smaller than 6 MB", quotation_status="not_collected")
        return record
    record.update(image_sha256=hashlib.sha256(body).hexdigest(), image_bytes=len(body), image_format=image_format, last_modified=modified)
    path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="owspace-meta-", suffix=".jpg", delete=False) as tmp:
            tmp.write(body)
            path = tmp.name
        if not hasattr(local, "ocr"):
            local.ocr = subprocess.Popen([args.ocr], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
            processes.append(local.ocr)
        local.ocr.stdin.write(json.dumps({"path": path, "year": date.year}) + "\n")
        local.ocr.stdin.flush()
        ocr = json.loads(local.ocr.stdout.readline())
        if "error" in ocr:
            raise RuntimeError(ocr["error"])
        record.update(parse_metadata(ocr), status="indexed")
    except Exception as exc:
        record.update(status="ocr_error", error=str(exc), quotation_status="not_collected")
    finally:
        if path:
            Path(path).unlink(missing_ok=True)
    return record


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def run(args):
    if args.start[:4] != args.end[:4]:
        raise SystemExit("Process one year at a time; review it before starting the next year")
    year = int(args.start[:4])
    if not (ROOT / "years" / f"{year}-layout.json").exists():
        raise SystemExit("Annual layout analysis is required before extraction")
    if year > 2015:
        previous = ROOT / "years" / f"{year-1}-review.json"
        if not previous.exists() or not json.loads(previous.read_text())["date_coverage_pass"]:
            raise SystemExit("The preceding year must pass the date coverage review first")
    if args.commit and git("branch", "--show-current") != BRANCH:
        raise SystemExit("Refusing to commit on an unexpected branch")
    directory = ROOT / "months"
    directory.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for year in range(2015, 2026):
            for month in range(1, 13):
                key = f"{year}-{month:02d}"
                if key < args.start or key > args.end:
                    continue
                target = directory / f"{key}.jsonl"
                rows = {r["date"]: r for r in map(json.loads, target.read_text().splitlines())} if target.exists() else {}
                dates = [dt.date(year, month, day) for day in range(1, calendar.monthrange(year, month)[1] + 1)]
                todo = [d for d in dates if args.refresh or str(d) not in rows or rows[str(d)]["status"] in ("request_error", "ocr_error", "unexpected_response")]
                futures = {pool.submit(one, d, args): d for d in todo}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    rows[result["date"]] = result
                    temporary = target.with_suffix(".tmp")
                    temporary.write_text("".join(json.dumps(rows[d], ensure_ascii=False) + "\n" for d in sorted(rows)), encoding="utf-8")
                    temporary.replace(target)
                statuses = {s: sum(r["status"] == s for r in rows.values()) for s in sorted({r["status"] for r in rows.values()})}
                print(json.dumps({"month": key, "records": len(rows), "statuses": statuses}, ensure_ascii=False), flush=True)
                if args.commit:
                    if git("branch", "--show-current") != BRANCH:
                        raise SystemExit("Branch changed during indexing")
                    rel = str(target.relative_to(ROOT))
                    git("add", "--", rel)
                    if git("diff", "--cached", "--name-only", "--", rel):
                        git("commit", "--only", "-m", f"data(owspace): index {key} calendar metadata", "--", rel)
    for process in processes:
        process.stdin.close()
        process.wait(timeout=10)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2015-01")
    p.add_argument("--end", default="2015-12")
    p.add_argument("--ocr", default="/tmp/owspace-research/ocr_metadata")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--interval", type=float, default=.25, help="Global minimum seconds between HTTP requests")
    p.add_argument("--commit", action="store_true")
    p.add_argument("--refresh", action="store_true", help="Re-extract an existing month after changing annual rules")
    run(p.parse_args())
