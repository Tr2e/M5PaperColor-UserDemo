#!/usr/bin/env python3
"""Read PaperColor display metrics over its runtime USB CDC interface."""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
import time
from pathlib import Path

import serial

from collect_display_metrics import FIELDS, parse_lines, parse_pipeline, summarize


def find_port() -> str:
    candidates = sorted(glob.glob("/dev/cu.usbmodem*"))
    if len(candidates) != 1:
        shown = ", ".join(candidates) if candidates else "none"
        raise RuntimeError(f"expected one /dev/cu.usbmodem* port, found: {shown}")
    return candidates[0]


def read_capture(port: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    with serial.Serial(port, 115200, timeout=0.2, write_timeout=1) as device:
        device.reset_input_buffer()
        device.write(b"metrics\n")
        device.flush()
        while time.monotonic() < deadline:
            chunk = device.read(1024)
            if chunk:
                chunks.append(chunk)
                if b"DisplayMetricsEnd" in b"".join(chunks):
                    break
    return b"".join(chunks).decode("utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="runtime CDC port; auto-detected when omitted")
    parser.add_argument("--timeout", type=float, default=5.0, help="response timeout in seconds")
    parser.add_argument("--raw", type=Path, help="write the raw CDC response")
    parser.add_argument("--csv", type=Path, help="write parsed records as CSV")
    parser.add_argument("--summary", type=Path, help="write aggregate JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        port = args.port or find_port()
        capture = read_capture(port, args.timeout)
    except (RuntimeError, serial.SerialException) as error:
        print(f"USB metrics read failed: {error}", file=sys.stderr)
        return 2

    if args.raw:
        args.raw.write_text(capture, encoding="utf-8")

    capture_lines = capture.splitlines()
    records = parse_lines(capture_lines)
    if not records:
        print("No DisplayMetrics records returned", file=sys.stderr)
        return 1

    if args.csv:
        with args.csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)

    summary = summarize(records)
    pipeline = parse_pipeline(capture_lines)
    if pipeline:
        summary["pipeline"] = pipeline
    if args.summary:
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    else:
        json.dump(summary, sys.stdout, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
