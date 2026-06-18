#!/usr/bin/env python3
"""Persist seed-free CV rep counts into a COMMITTED CSV so they survive container restarts.

The eval boards write to /tmp logs (ephemeral). A container restart wipes them, forcing a
multi-hour full re-score every session — the exact "lost work" trap. This merges board-log
lines (the `_trackc_check.py` / `cv_eval.py` format) into `dataset/cv_seedfree_scores.csv`,
the durable source `scripts/inventory.py` reads. Idempotent: a later score for a set_id
overwrites the earlier one.

    python dataset/tools/persist_cv_scores.py /tmp/direct.log [more logs ...]
    python dataset/tools/persist_cv_scores.py            # default: common /tmp board logs
"""
from __future__ import annotations
import csv, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
CSV_PATH = os.path.join(DATASET, "cv_seedfree_scores.csv")
COLS = ["set_id", "seed_free_count", "source"]

# board line: "20260617-SQ-1   main  10   5(-5)   5 False  True  flow;"  -> grab the 4th col count
BOARD_RE = re.compile(r"^\s*(\d{8}-\w+-\d+)\s+\w+\s+\d+\s+(\d+)\(")
# transcode_proxy line: "20260613-DL-1   3840x2160 ... reps=6 ..."
PROXY_RE = re.compile(r"^\s*(\d{8}-\w+-\d+)\s+\d+x\d+.*reps=(\d+)")


def load():
    out = {}
    if os.path.exists(CSV_PATH):
        for r in csv.DictReader(open(CSV_PATH)):
            out[r["set_id"]] = r
    return out


def main():
    logs = sys.argv[1:] or ["/tmp/direct.log", "/tmp/strict_full.log", "/tmp/r2_check.log",
                            "/tmp/transcode.log"]
    rows = load()
    src_tag = os.environ.get("SCORE_SOURCE", "board re-score")
    added = 0
    for fn in logs:
        if not os.path.exists(fn):
            continue
        for line in open(fn):
            line = re.sub(r"\x1b\[[0-9;]*m", "", line)
            m = BOARD_RE.match(line) or PROXY_RE.match(line)
            if not m:
                continue
            sid, cnt = m.group(1), int(m.group(2))
            rows[sid] = {"set_id": sid, "seed_free_count": cnt, "source": src_tag}
            added += 1
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for sid in sorted(rows):
            w.writerow({c: rows[sid].get(c, "") for c in COLS})
    print(f"persisted {len(rows)} seed-free scores ({added} parsed) -> {CSV_PATH}")


if __name__ == "__main__":
    main()
