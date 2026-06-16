"""EXPERIMENT (2026-06-16): position-cycle rep detection for the paused/supine bench
watch IMU — the segmentation lever for per-rep velocity.

The PoC velocity-crossing `detect_turnarounds` OVER-segments the bench pauses (chest
hold, lockout hold) → per-rep MV r≈0.59, RMSE 0.091 vs Vitruve (below the SEE<0.07
target). ROM is already good (~0.31 vs 0.33 m), so displacement is captured; the gap
is delimiting the concentric amid the pauses. This detector EXPLOITS the pauses
instead: high-pass the doubly-integrated position (drift out), find chest MINIMA and
lockout MAXIMA, and take the mean |drift-removed velocity| over each bottom→top.

Result: per-rep r 0.82–0.95 on the sets it segments cleanly (BN-3 r=0.95) — proving
the lever is SEGMENTATION, not the hardware (Achermann hit r>0.97). NOT production-
ready: no single `prominence` robustly hits exact-10 AND high-r across all 5 sets
(loose→noisy reps, tight→missed reps). Next unlocks: Madgwick orientation fusion for
cleaner world-vertical accel, a learned rep detector, the Achermann 100 Hz protocol.
"""
import sys, csv, numpy as np
sys.path.insert(0, "analysis")
from vbt_analysis.ingest import load_session
from vbt_analysis.velocity import vertical_acceleration
from scipy.signal import savgol_filter, find_peaks, butter, filtfilt
from scipy.integrate import cumulative_trapezoid


def vit(sid, m):
    return np.array([float(r['value']) for r in csv.DictReader(open('dataset/rep_metrics.csv'))
                     if r['set_id'] == sid and r['vendor'] == 'vitruve' and r['metric'] == m and r['rep_index']])


def reps_poscycle(t, a, fs, prom=0.3, dist=1.5):
    """Return per-rep mean |drift-removed vertical velocity| via position cycles."""
    v = cumulative_trapezoid(a, t, initial=0)
    b, al = butter(2, 0.1 / (fs / 2), 'high'); vhp = filtfilt(b, al, v)
    pos = cumulative_trapezoid(vhp, t, initial=0)
    b2, al2 = butter(2, 0.05 / (fs / 2), 'high')
    poss = savgol_filter(filtfilt(b2, al2, pos), int(fs * 0.3) | 1, 2)
    rng = np.percentile(poss, 95) - np.percentile(poss, 5)
    mins, _ = find_peaks(-poss, distance=int(fs * dist), prominence=prom * rng)
    maxs, _ = find_peaks(poss, distance=int(fs * dist), prominence=prom * rng)
    mvs = []
    for bi in mins:
        tops = maxs[maxs > bi]
        if len(tops) == 0 or (tops[0] - bi) < int(fs * 0.2):
            continue
        mvs.append(np.mean(np.abs(vhp[bi:tops[0] + 1])))
    return np.array(mvs)


if __name__ == "__main__":
    for s in range(1, 6):
        sid = f"20260616-BN-{s}"
        df = load_session(f"dataset/raw/20260616-BN-{s}_watch.csv")
        t = df["t"].to_numpy(float); a = vertical_acceleration(df); fs = 1.0 / np.median(np.diff(t))
        vmv = vit(sid, 'mean_velocity')
        mvs = reps_poscycle(t, a, fs, prom=0.3)
        n = min(len(mvs), len(vmv))
        r = np.corrcoef(mvs[:n], vmv[:n])[0, 1] if n >= 8 else float('nan')
        print(f"{sid}: pos-cycle reps={len(mvs)} (GT {len(vmv)}) per-rep r={r:.2f}")
