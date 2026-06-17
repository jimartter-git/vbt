"""Extend the four-input per-rep scoreboard with the 06-17 squats + RDLs.

3/4 inputs (Vitruve GT + Apple Watch IMU + our-CV video; no SmartBarbell). CV is
count-only here (auto counts in clips.csv; abs m/s hub-inflated, no rim registered).
Watch is run fresh through vbt_analysis: Watch-auto (raw detect_turnarounds) and
Watch-adj (the gating ingest_watch_imu uses: squat->gate_reps, rdl->ROM window).
"""
import sys, os, csv, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from vbt_analysis.ingest import load_session
from vbt_analysis.velocity import (vertical_acceleration, integrate_with_zupt,
                                   rep_metrics, gate_reps)
from vbt_analysis.rep_detect import detect_turnarounds
from vbt_analysis.agreement import compare_panel

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SETS = [("20260617-SQ-1", "squat", 10), ("20260617-SQ-2", "squat", 10),
        ("20260617-SQ-3", "squat", 10), ("20260617-SQ-4", "squat", 10),
        ("20260617-RDL-1", "rdl", 8), ("20260617-RDL-2", "rdl", 8)]
# CV auto counts (clips.csv, count-only — abs m/s hub-inflated, no rim)
CV_COUNT = {"20260617-SQ-1": 5, "20260617-SQ-2": 10, "20260617-SQ-3": 10,
             "20260617-SQ-4": 10, "20260617-RDL-1": 8, "20260617-RDL-2": 8}


def vit(sid, metric="mean_velocity"):
    return [float(r['value']) for r in csv.DictReader(open(os.path.join(REPO, 'dataset/rep_metrics.csv')))
            if r['set_id'] == sid and r['vendor'] == 'vitruve' and r['metric'] == metric and r['rep_index']]


def watch_reps(sid, lift, gate):
    df = load_session(os.path.join(REPO, f"dataset/raw/{sid}_watch.csv"))
    t = df["t"].to_numpy(float); a = vertical_acceleration(df)
    anchors = detect_turnarounds(t, a); v = integrate_with_zupt(t, a, anchors)
    reps = rep_metrics(t, v, anchors)
    if not gate:
        return reps
    if lift in ("row", "squat"):
        return gate_reps(reps)
    if lift == "rdl":
        return [r for r in reps if 0.40 <= r.range_of_motion <= 0.70 and r.mean_concentric_velocity > 0.10]
    return reps


for sid, lift, gt in SETS:
    vmv = vit(sid)
    auto = watch_reps(sid, lift, gate=False)
    adj = watch_reps(sid, lift, gate=True)
    a_mv = [r.mean_concentric_velocity for r in auto]
    j_mv = [r.mean_concentric_velocity for r in adj]
    j_rom = [r.range_of_motion for r in adj]
    print(f"\n========== {sid}  ({lift}, GT {gt}) ==========")
    print(f"  counts:  Vitruve {len(vmv)}  CV-auto {CV_COUNT[sid]}  Watch-auto {len(auto)}  Watch-adj {len(adj)}")
    print(f"  Vitruve MV : {[round(x,3) for x in vmv]}")
    print(f"  Watch-adj  : {[round(x,3) for x in j_mv]}")
    print(f"  Watch-adj ROM m: {[round(x,2) for x in j_rom]}")
    for name, mv in (("SmartBarbell", None), ("CV-auto(count-only)", None),
                     ("Watch-auto", a_mv), ("Watch-adj", j_mv)):
        if mv is None:
            continue
        p = compare_panel(mv, vmv)
        rmse = f"{p['rmse']:.3f}" if p['aligned'] else "— (count≠)"
        bias = f"{p['bias']:+.3f}" if p['aligned'] else "—"
        print(f"    {name:<12} n {p['n_source']}/{p['n_ref']}  RMSE {rmse}  bias {bias}  "
              f"VL {p['vl_source']:.1f}->{p['vl_ref']:.1f} (Δ{p['vl_delta']:+.1f}pp)  "
              f"slope {p['slope_source']:+.3f}->{p['slope_ref']:+.3f} (Δ{p['slope_delta']:+.3f})")

# aggregate watch-adj vs vitruve (count-matched sets only)
print("\n\n===== AGGREGATE Watch-adj vs Vitruve (count-matched sets) =====")
allw, allv = [], []
for sid, lift, gt in SETS:
    vmv = vit(sid); adj = [r.mean_concentric_velocity for r in watch_reps(sid, lift, gate=True)]
    if len(adj) == len(vmv):
        allw += adj; allv += vmv
allw, allv = np.array(allw), np.array(allv)
print(f"n={len(allw)} reps  bias {np.mean(allw-allv):+.3f}  RMSE {np.sqrt(np.mean((allw-allv)**2)):.3f}  r {np.corrcoef(allw,allv)[0,1]:.3f}")
print("(target r>0.95 SEE<0.07)")
