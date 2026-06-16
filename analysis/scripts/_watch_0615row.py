"""First real watch-IMU vs Vitruve comparison: 2026-06-15 barbell rows (5 sets)."""
import sys, os, csv, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from vbt_analysis.ingest import load_session
from vbt_analysis.velocity import vertical_acceleration, integrate_with_zupt, rep_metrics
from vbt_analysis.rep_detect import detect_turnarounds
from vbt_analysis.metrics import velocity_loss_pct

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def vit(sid, metric):
    return np.array([float(r['value']) for r in csv.DictReader(open(os.path.join(REPO,'dataset/rep_metrics.csv')))
                     if r['set_id']==sid and r['vendor']=='vitruve' and r['metric']==metric and r['rep_index']])

for s in range(1, 6):
    sid = f"20260615-ROW-{s}"
    df = load_session(os.path.join(REPO, f"dataset/raw/20260615-ROW-{s}_watch.csv"))
    t = df["t"].to_numpy(float)
    a = vertical_acceleration(df)
    anchors = detect_turnarounds(t, a)
    v = integrate_with_zupt(t, a, anchors)
    reps = rep_metrics(t, v, anchors)
    mv = np.array([r.mean_concentric_velocity for r in reps])
    rom = np.array([r.range_of_motion for r in reps])
    vmv = vit(sid, 'mean_velocity'); vrom = vit(sid, 'rom')/100.0
    wl = velocity_loss_pct(list(mv)); vl = velocity_loss_pct(list(vmv))
    fs = 1.0/np.median(np.diff(t))
    print(f"\n=== {sid}  ({len(t)} samples @ {fs:.0f}Hz, {t[-1]-t[0]:.1f}s) ===")
    print(f"  reps: watch {len(reps)}  vs Vitruve {len(vmv)}")
    print(f"  watch MV : {[round(x,2) for x in mv]}")
    print(f"  Vitruve  : {[round(x,2) for x in vmv]}")
    print(f"  watch ROM m: {[round(x,2) for x in rom]}  (Vit ~{np.median(vrom):.2f})")
    print(f"  velocity-LOSS: watch {wl:.1f}%  Vitruve {vl:.1f}%")
    if len(mv) == len(vmv) and len(mv) > 1:
        r = np.corrcoef(mv, vmv)[0, 1]
        print(f"  per-rep: r={r:.3f}  bias={np.mean(mv-vmv):+.3f}  SEE/RMSE={np.sqrt(np.mean((mv-vmv)**2)):.3f} m/s")

print("\n\n############ CLEAN-REP ALIGNMENT (drop setup/trailing junk: keep 0.35<=ROM<=0.9 m) ############")
allw, allv = [], []
for s in range(1, 6):
    sid = f"20260615-ROW-{s}"
    df = load_session(os.path.join(REPO, f"dataset/raw/20260615-ROW-{s}_watch.csv"))
    t = df["t"].to_numpy(float); a = vertical_acceleration(df)
    anchors = detect_turnarounds(t, a); v = integrate_with_zupt(t, a, anchors)
    reps = rep_metrics(t, v, anchors)
    clean = [r for r in reps if 0.35 <= r.range_of_motion <= 0.9 and r.mean_concentric_velocity > 0.35]
    mv = np.array([r.mean_concentric_velocity for r in clean])
    vmv = vit(sid, 'mean_velocity')
    print(f"{sid}: clean watch reps {len(clean)} vs Vitruve {len(vmv)}", end="")
    n = min(len(mv), len(vmv))
    if n >= 8:
        # align tail-anchored (both are the same set; compare the last n)
        w, vv = mv[-n:], vmv[-n:]
        allw += list(w); allv += list(vv)
        print(f"  | per-rep(last {n}) bias={np.mean(w-vv):+.3f} RMSE={np.sqrt(np.mean((w-vv)**2)):.3f} r={np.corrcoef(w,vv)[0,1]:.2f}")
    else:
        print("  (count off, skip per-rep)")
allw, allv = np.array(allw), np.array(allv)
print(f"\nAGGREGATE clean reps n={len(allw)}: bias={np.mean(allw-allv):+.3f}  SEE/RMSE={np.sqrt(np.mean((allw-allv)**2)):.3f} m/s  r={np.corrcoef(allw,allv)[0,1]:.3f}")
print("(project target: r>0.95, SEE<0.07 m/s)")
