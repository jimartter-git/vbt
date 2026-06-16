"""Plot watch IMU rows so we can SEE the reps — accel, velocity, position."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt
from vbt_analysis.ingest import load_session
from vbt_analysis.velocity import vertical_acceleration
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def hp(v, fs, cut):
    b, a = butter(2, min(0.99, cut/(fs/2)), btype="high"); return filtfilt(b, a, v)

def panel(ax, t, y, title, color):
    ax.plot(t - t[0], y, color, lw=0.8); ax.set_title(title, fontsize=9, loc="left")
    ax.axhline(0, color="gray", lw=0.5, alpha=0.5); ax.grid(alpha=0.2)

for s in [3, 5]:
    df = load_session(os.path.join(REPO, f"dataset/raw/20260615-ROW-{s}_watch.csv"))
    t = df["t"].to_numpy(float); a = vertical_acceleration(df); fs = 1/np.median(np.diff(t))
    vel = hp(cumulative_trapezoid(a, t, initial=0.0), fs, 0.10)        # drift-removed velocity
    pos = hp(cumulative_trapezoid(vel, t, initial=0.0), fs, 0.10)      # drift-removed position
    fig, ax = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    panel(ax[0], t, a, f"ROW-{s}  vertical acceleration (m/s2)", "tab:red")
    panel(ax[1], t, vel, "vertical velocity (drift-removed, m/s)  <- count the +lobes", "tab:blue")
    panel(ax[2], t, pos, "vertical position (drift-removed, m)  <- count the up-down cycles", "tab:green")
    ax[2].set_xlabel("time (s)")
    fig.suptitle(f"20260615-ROW-{s} watch IMU  (Vitruve GT = 10 reps)", fontsize=11)
    fig.tight_layout()
    out = f"/tmp/frames/watch_ROW{s}.png"; fig.savefig(out, dpi=110); plt.close(fig)
    print("saved", out)
