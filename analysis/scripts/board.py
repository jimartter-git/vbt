#!/usr/bin/env python3
"""Cross-vendor board — every set that has a video, all vendors, rep count + velocity.

One matrix: rows = sets with a video clip, columns = each vendor that measured it
(Vitruve / Stance / SmartBarbell / Metric / WL) plus OUR live CV (mevbt_cv, run now
from the clip via the cv_eval seeds). Cells are `reps·mean_m/s`; blank (—) = that
vendor has no data for that set (the gaps). `?` on a velocity = our scale flagged it.

    python analysis/scripts/board.py            # full board (runs our CV live)
    python analysis/scripts/board.py --no-cv    # dataset vendors only (fast)
"""
from __future__ import annotations
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cv_eval import CLIPS, run  # noqa: E402  (reuse the per-clip seeds + live pipeline)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET = os.path.join(REPO, "dataset")

# Column order: ground truth first, then on-bar BLE apps, then phone-CV apps, then ours.
VENDORS = ["vitruve", "stance", "smartbarbell", "metric", "wl_analysis"]
HEAD = {"vitruve": "Vitruve", "stance": "Stance", "smartbarbell": "SmartB",
        "metric": "Metric", "wl_analysis": "WL", "ours": "Ours(CV)"}


def load():
    reps = list(csv.DictReader(open(os.path.join(DATASET, "rep_metrics.csv"))))
    sets = {s["set_id"]: s for s in csv.DictReader(open(os.path.join(DATASET, "sets.csv")))}
    vids = [r["set_id"] for r in csv.DictReader(open(os.path.join(DATASET, "raw_files.csv")))
            if r.get("kind", "").startswith("video")]
    return reps, sets, vids


def cell(reps, set_id, vendor):
    """`reps·mean` for one (set, vendor), excluding phantom rows. None if no data."""
    rows = [r for r in reps if r["set_id"] == set_id and r["vendor"] == vendor
            and r["metric"] == "mean_velocity" and (r["flag"] or "") != "phantom"]
    if not rows:
        return None
    n = len(rows)
    mean = sum(float(r["value"]) for r in rows) / n
    undercount = any(r["flag"] == "undercount" for r in rows)
    return f"{n}{'!' if undercount else ''}·{mean:.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-cv", action="store_true", help="skip the live CV column")
    args = ap.parse_args()
    reps, sets, vids = load()
    # keep dataset order but stable: sort by set_id
    vids = sorted(set(vids))

    print("\nVBT cross-vendor board — sets with video.  cell = reps·mean(m/s)   "
          "(— no data, ! undercount, ? scale-flagged)\n")
    cols = VENDORS + (["ours"] if not args.no_cv else [])
    hdr = f"{'set':<15}{'lift':<13}{'load':>7}  " + "".join(f"{HEAD[v]:>10}" for v in cols)
    print(hdr); print("-" * len(hdr))
    for sid in vids:
        s = sets.get(sid, {})
        lift = (s.get("lift", "") or "")[:12]
        loadstr = f"{s.get('load_entered','')}{s.get('load_unit','')}"
        line = f"{sid:<15}{lift:<13}{loadstr:>7}  "
        for v in VENDORS:
            line += f"{(cell(reps, sid, v) or '—'):>10}"
        if not args.no_cv:
            c = "—"
            if sid in CLIPS:
                clip_rel, trackers, _note, band = CLIPS[sid]
                seed = trackers.get("flow")
                try:
                    n, mean, _conf, suspect = run(os.path.join(REPO, clip_rel), "flow",
                                                  seed, adaptive=True, band=band)
                    c = f"{n}·{mean:.2f}{'?' if suspect else ''}"
                except Exception as e:
                    c = f"ERR"
                    print(f"   ! {sid} CV: {type(e).__name__}: {e}", file=sys.stderr)
            line += f"{c:>10}"
        print(line)
    print("\nGround truth = Vitruve where present (on-bar device); IB-1 reference = the "
          "3-way Stance/SmartB/WL agreement. Our CV (Ours) is the live pipeline via the "
          "cv_eval seeds. Counts that disagree are the rep-detection story; the spread in "
          "the velocity halves is the calibration story.")


if __name__ == "__main__":
    main()
