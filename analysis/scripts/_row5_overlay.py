"""Overlay the ROW-5 BAR cadence (video) on the WATCH signal — same time axis."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt, find_peaks
from vbt_video.frames import PyAVDecoder
from vbt_video.track import FlowTracker
from vbt_analysis.ingest import load_session
from vbt_analysis.velocity import vertical_acceleration
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def hp(v, fs, cut):
    b, a = butter(2, min(0.99, cut/(fs/2)), btype="high"); return filtfilt(b, a, v)

# --- BAR from video: y-position trace (auto-seed flow that gave 10/10) ---
src = PyAVDecoder("/tmp/row0615_proxy/20260615-ROW-5.mp4")
from vbt_video.track import auto_seed_motion
fl = FlowTracker().track(src, auto_seed_motion(src))
bt = fl.traj[:, 0].astype(float); by = -fl.traj[:, 2].astype(float)   # up = +
by = by - by.mean()
# bar concentric peaks = top of each row (bar pulled up); count cadence
bpk, _ = find_peaks(by, distance=int(0.4*src.fps), prominence=0.25*np.ptp(by))
bt0 = bt - bt[0]

# --- WATCH ---
df = load_session(os.path.join(REPO, "dataset/raw/20260615-ROW-5_watch.csv"))
wt = df["t"].to_numpy(float); a = vertical_acceleration(df); fs = 1/np.median(np.diff(wt))
ua = df[["ua_x","ua_y","ua_z"]].to_numpy(float)*9.80665; mag = np.linalg.norm(ua, axis=1)
wvel = hp(cumulative_trapezoid(a, wt, initial=0.0), fs, 0.10)
wt0 = wt - wt[0]
wpk, _ = find_peaks(wvel, distance=int(0.4*fs), prominence=0.15*np.ptp(wvel))

print(f"VIDEO bar: {len(bpk)} rep peaks, span {bt0[bpk][0]:.1f}-{bt0[bpk][-1]:.1f}s, "
      f"cadence {np.mean(np.diff(bt0[bpk])):.2f}s/rep")
print(f"WATCH vel: {len(wpk)} peaks, cadence {np.mean(np.diff(wt0[wpk])):.2f}s/rep")
print("VIDEO rep times:", [round(x,1) for x in bt0[bpk]])
print("WATCH pk  times:", [round(x,1) for x in wt0[wpk]])

fig, ax = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
ax[0].plot(bt0, by, "tab:green"); ax[0].plot(bt0[bpk], by[bpk], "kv")
ax[0].set_title(f"VIDEO: bar vertical position — {len(bpk)} reps", loc="left", fontsize=10)
ax[1].plot(wt0, wvel, "tab:blue"); ax[1].plot(wt0[wpk], wvel[wpk], "rv")
ax[1].set_title(f"WATCH: vertical velocity — {len(wpk)} peaks", loc="left", fontsize=10)
ax[2].plot(wt0, mag, "k", lw=0.7)
ax[2].set_title("WATCH: |userAccel| magnitude (orientation-free)", loc="left", fontsize=10)
for x in bt0[bpk]:
    for r in range(3): ax[r].axvline(x, color="green", ls=":", alpha=0.4)
ax[2].set_xlabel("time from first rep (s)")
for r in range(3): ax[r].grid(alpha=0.2)
fig.suptitle("ROW-5: bar cadence (green dotted = video rep tops) vs watch wrist signal")
fig.tight_layout(); fig.savefig("/tmp/frames/row5_overlay.png", dpi=110); print("saved")
