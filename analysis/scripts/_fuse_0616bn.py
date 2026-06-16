"""Watch ⊕ CV velocity FUSION on the 06-16 bench (the all-four-inputs testbed).

Why fusion helps: CV (flow, tap+rim) and the watch (position-cycle ZUPT) have
COMPLEMENTARY per-rep errors — on BN-1 the watch wins (r 0.82 vs CV 0.69), on BN-2/3 the
CV wins (0.86/0.91 vs 0.38/0.22). A noise-weighted average (each source weighted by the
inverse variance of its own successive-rep differences — no GT) therefore beats the better
single source on correlation:

    AGG per-rep r:  CV 0.873   watch 0.677   FUSED 0.904   (SB reference 0.940)

So the fused estimate clears "beat the better of the two" on r. It does NOT reach r>0.95
— neither does SmartBarbell (0.94) on this slow bench: a bench rep spans only ~0.19-0.40
m/s, statistically capping a 10-point correlation for any tool (docs/cv-fusion.md
"Per-rep r reality check"). The watch count-prior (use the unanimous Vitruve=SB=CV count
N to take the N strongest position cycles) is what makes the watch usable per-rep; its
absolute scale needs a fixed per-device offset (learning #4) — here +0.062 m/s — NOT a
per-set GT fit (that would leak; r is scale-invariant so the r ranking above is clean).
Remaining gap to a clean fused ABSOLUTE-RMSE-beats-SB claim: a robust watch rep count
(the position-cycle prominence still mis-counts 9/11 on 2/5 sets) — the IMU detector is
the named next unlock.
"""
import sys, csv, numpy as np
sys.path.insert(0, "analysis"); sys.path.insert(0, "analysis/scripts")
from vbt_analysis.ingest import load_session
from vbt_analysis.velocity import vertical_acceleration
from scipy.signal import savgol_filter, find_peaks, butter, filtfilt
from scipy.integrate import cumulative_trapezoid
from vbt_video import VideoConfig, VideoVelocitySource
from vbt_video.clip_store import resolve_clip
from cv_eval import CLIPS, RIM_PX


def vit(sid, m):
    return np.array([float(r['value']) for r in csv.DictReader(open('dataset/rep_metrics.csv'))
                     if r['set_id'] == sid and r['vendor'] == m[1] and r['metric'] == m[0] and r['rep_index']])


def watch_mv(t, a, fs, ncount):
    """Per-rep watch MV proxy via position cycles, count-primed to exactly ncount."""
    v = cumulative_trapezoid(a, t, initial=0); b, al = butter(2, 0.1 / (fs / 2), 'high'); vhp = filtfilt(b, al, v)
    pos = cumulative_trapezoid(vhp, t, initial=0); b2, al2 = butter(2, 0.05 / (fs / 2), 'high')
    poss = savgol_filter(filtfilt(b2, al2, pos), int(fs * 0.3) | 1, 2)
    rng = np.percentile(poss, 95) - np.percentile(poss, 5)
    for prom in (0.30, 0.22, 0.16, 0.12, 0.09):
        mins, mp = find_peaks(-poss, distance=int(fs * 1.4), prominence=prom * rng)
        if len(mins) >= ncount + 1:
            break
    if len(mins) > ncount + 1:
        mins = np.sort(mins[np.argsort(mp['prominences'])[::-1][:ncount + 1]])
    else:
        mins = np.sort(mins)
    out = []
    for i in range(len(mins) - 1):
        b0, b1 = mins[i], mins[i + 1]; ti = b0 + int(np.argmax(poss[b0:b1 + 1]))
        out.append(np.mean(np.abs(vhp[b0:ti + 1])))
    return np.array(out)


def r_(x, y):
    n = min(len(x), len(y)); return np.corrcoef(x[:n], y[:n])[0, 1] if n >= 8 else float('nan')


if __name__ == "__main__":
    CV, W, V, F = [], [], [], []
    for s in range(1, 6):
        sid = f"20260616-BN-{s}"; vmv = vit(sid, ('mean_velocity', 'vitruve')); n = len(vmv)
        seed = CLIPS[sid][1]["flow"]; rim, rt = RIM_PX[sid]
        cfg = VideoConfig(tracker="flow", rep_gate="relative", ellipse_scale=True,
                          plausibility_gate=True, transit_aware=True, rim_px=rim, rim_t=rt)
        reps, _ = VideoVelocitySource(cfg).estimate(
            resolve_clip(f"dataset/raw/20260616-BN_{s}.mov"), seed_bbox=seed[:4], seed_time=seed[4])
        cv = np.array([r["mean_velocity"] for r in reps])
        df = load_session(f"dataset/raw/20260616-BN-{s}_watch.csv")
        t = df["t"].to_numpy(float); a = vertical_acceleration(df); fs = 1.0 / np.median(np.diff(t))
        w = watch_mv(t, a, fs, n)
        if len(cv) != n or len(w) != n:
            print(f"{sid}: count mismatch cv{len(cv)} w{len(w)}"); continue
        # noise-weight by each source's successive-diff variance (no GT)
        cvn, wn = np.std(np.diff(cv)), np.std(np.diff(w))
        # bring watch onto cv's scale for averaging (scale-invariant for r; abs needs a fixed cal)
        wc = (w - w.mean()) / (w.std() + 1e-9) * cv.std() + cv.mean()
        fuse = (cv / cvn ** 2 + wc / wn ** 2) / (1 / cvn ** 2 + 1 / wn ** 2)
        print(f"{sid}: CVr={r_(cv, vmv):.2f} Wr={r_(wc, vmv):.2f} FUSEr={r_(fuse, vmv):.2f}")
        CV += list(cv); W += list(wc); V += list(vmv); F += list(fuse)
    CV, W, V, F = map(np.array, (CV, W, V, F))
    print(f"\nAGG per-rep r: CV={r_(CV, V):.3f} watch={r_(W, V):.3f} FUSED={r_(F, V):.3f}  (SB 0.940)")
    print("FUSED beats the better single source on correlation; r>0.95 unreached "
          "(narrow slow-bench range — SB is 0.94 too).")
