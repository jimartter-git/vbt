"""Ingest the 2026-07-01 Barbell Squat Vitruve export — a MESSY, TWO-ATHLETE file.

The single export (dataset/raw/20260701-SQ_vitruve_MMJM.csv) was recorded on the
owner's Vitruve account, so every row reads Athlete "j mart" — but two lifters shared
the session: the owner (JM) and his wife (MM). The split is by the lifter's own word,
corroborated by load (MM = the only two 185 lb sets; JM = 225-265 lb):

    Vitruve # Set:   1     2     3     4     5     6     7
    lifter:          MM    JM    MM    JM    JM    JM    JM
    load (lb):       185   265   185   225   225   235   235
    reps:            6     10    10    10    10    10    10

The watch-extract numbering references EACH LIFTER's own set index (not the Vitruve
# Set), so we remap to per-lifter set_ids that the watch files already match:

    JM: Vitruve {2,4,5,6,7} -> set_id 20260701-SQ-{1,2,3,4,5}
        (JM set 5 == Vitruve set 7, per the owner)  watch: SQ-2_watch, SQ-5_watch
    MM: Vitruve {1,3}       -> set_id 20260701-SQ-MM-{1,2}   (matches 06-19 SQ-MM naming)
        watch (bar-sleeve mount): SQ-MM-1_watch_bar, SQ-MM-2_watch_bar

RPE not provided -> blank. Idempotent: strips prior rows for the produced set_ids first.
Run from repo root:  python dataset/tools/_ingest_0701sq_vitruve.py
"""
from __future__ import annotations
import csv, os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "dataset", "raw", "20260701-SQ_vitruve_MMJM.csv")
SETS = os.path.join(REPO, "dataset", "sets.csv")
REPS = os.path.join(REPO, "dataset", "rep_metrics.csv")
LB_PER_KG = 0.45359

MET = [
    ("Mean Velocity (m/s)", "mean_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Mean Propulsive Velocity (m/s)", "mean_propulsive_velocity", "m/s", lambda x: round(float(x), 3)),
    ("Peak Velocity (m/s)", "peak_velocity", "m/s", lambda x: round(float(x), 3)),
    ("ROM (Range of Motion) (m)", "rom", "cm", lambda x: round(float(x) * 100, 1)),
    ("Mean Power [MV] (W)", "mean_power", "W", lambda x: round(float(x), 2)),
    ("Peak Power (W)", "peak_power", "W", lambda x: round(float(x), 2)),
    ("Time to Peak Velocity (ms)", "time_to_peak", "s", lambda x: round(float(x) / 1000, 3)),
]

# Vitruve # Set -> (set_id, lifter tag, note-context). Owner's stated split.
MAP = {
    "1": ("20260701-SQ-MM-1", "MM", "bar-sleeve watch (20260701-SQ-MM-1_watch_bar.csv)"),
    "3": ("20260701-SQ-MM-2", "MM", "bar-sleeve watch (20260701-SQ-MM-2_watch_bar.csv)"),
    "2": ("20260701-SQ-1",    "JM", "no watch this set (forgot to start)"),
    "4": ("20260701-SQ-2",    "JM", "wrist watch (20260701-SQ-2_watch.csv)"),
    "5": ("20260701-SQ-3",    "JM", "no watch this set (forgot to start)"),
    "6": ("20260701-SQ-4",    "JM", "no watch this set (forgot to start)"),
    "7": ("20260701-SQ-5",    "JM", "wrist watch (20260701-SQ-5_watch.csv)"),
}


def _rewrite_without(path, key_fn):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], [r for r in rows[1:] if not key_fn(r)]


def main() -> int:
    by_set = {}
    for r in csv.DictReader(open(SRC)):
        by_set.setdefault(r["# Set"].strip(), []).append(r)

    set_rows, rep_rows, made = [], [], []
    for vset in sorted(by_set, key=int):
        if vset not in MAP:
            raise SystemExit(f"unexpected Vitruve set {vset} — MAP covers only {sorted(MAP)}")
        sid, lifter, watch_ctx = MAP[vset]
        reps = by_set[vset]
        made.append(sid)
        load_kg = round(float(reps[0]["Weight (kg)"]), 1)
        load_lb = round(load_kg / LB_PER_KG)
        set_idx = sid.rsplit("-", 1)[1]
        who = "the owner (JM)" if lifter == "JM" else "the owner's wife (MM)"
        note = (f"Barbell Squat, 2026-07-01 — SHARED two-athlete session, {who}. "
                f"Vitruve GT (clean per-rep export), Vitruve source # Set {vset} @ {load_lb} lb, "
                f"{len(reps)} reps. Split from the mixed export "
                f"dataset/raw/20260701-SQ_vitruve_MMJM.csv by the owner's stated set map "
                f"(MM=Vitruve sets 1,3; JM=2,4,5,6,7), corroborated by load. RPE not provided. "
                f"{watch_ctx}. No SmartBarbell/video this session.")
        set_rows.append(dict(set_id=sid, date="2026-07-01", lift="squat", load_kg=load_kg,
                             load_entered=load_lb, load_unit="lb", set_index=set_idx,
                             target_reps="", actual_reps=len(reps), rpe_actual="", notes=note))
        for r in reps:
            rep = int(r["# Rep."])
            for col, metric, unit, fn in MET:
                v = r.get(col, "").strip()
                if v == "":
                    continue
                rep_rows.append(dict(set_id=sid, vendor="vitruve", rep_index=rep, true_rep=rep,
                                     metric=metric, value=fn(v), unit=unit, flag="", confidence=""))

    made_set = set(made)
    set_hdr, set_body = _rewrite_without(SETS, lambda r: r and r[0] in made_set)
    rep_hdr, rep_body = _rewrite_without(REPS, lambda r: r and r[0] in made_set and r[1] == "vitruve")
    with open(SETS, "w", newline="") as f:
        w = csv.writer(f); w.writerow(set_hdr)
        w.writerows([[sr[c] for c in set_hdr] for sr in set_rows]); w.writerows(set_body)
    with open(REPS, "w", newline="") as f:
        w = csv.writer(f); w.writerow(rep_hdr)
        w.writerows(rep_body); w.writerows([[rr[c] for c in rep_hdr] for rr in rep_rows])

    print(f"ingested {len(set_rows)} sets, {len(rep_rows)} vitruve rep rows")
    for sr in sorted(set_rows, key=lambda x: x["set_id"]):
        print(f"  {sr['set_id']:<20} {sr['load_entered']}lb x{sr['actual_reps']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
