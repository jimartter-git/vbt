"""All-pairs velocity cross-matching: which watch file aligns to which video?
Builds the fusion time-aligner and tests the label-reversal hypothesis."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, filtfilt
from vbt_video.frames import PyAVDecoder
from vbt_video.track import FlowTracker, auto_seed_motion, track_bidirectional
from vbt_analysis.ingest import load_session
from vbt_analysis.velocity import vertical_acceleration
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def hp(v, fs, cut):
    b, a = butter(2, min(0.99, cut/(fs/2)), btype="high"); return filtfilt(b, a, v)

SEEDS = {1: ((600,1110,130,130), 10.0), 2: ((525,1140,150,150), 6.0),
         3: ((580,1460,160,160), None), 4: ((519,1215,150,150), 6.0), 5: (None, None)}

def bar_vel(s):
    src = PyAVDecoder(f"/tmp/row0615_proxy/20260615-ROW-{s}.mp4")
    seed, st = SEEDS[s]
    if seed is None:
        tr = FlowTracker().track(src, auto_seed_motion(src))
    elif st is None:
        tr = FlowTracker().track(src, seed)
    else:
        tr = track_bidirectional(src, seed, st, lambda: FlowTracker())
    t = tr.traj[:, 0].astype(float); y = -tr.traj[:, 2].astype(float)
    v = np.gradient(y, t)
    return t - t[0], v, src.fps

def watch_vel(s):
    df = load_session(os.path.join(REPO, f"dataset/raw/20260615-ROW-{s}_watch.csv"))
    t = df["t"].to_numpy(float); a = vertical_acceleration(df); fs = 1/np.median(np.diff(t))
    v = hp(cumulative_trapezoid(a, t, initial=0.0), fs, 0.20)
    return t - t[0], v, fs

def best_xcorr(tw, vw, tv, vv):
    g = np.arange(0, max(tw[-1], tv[-1]), 0.02)
    a = np.interp(g, tw, vw, left=0, right=0); b = np.interp(g, tv, vv, left=0, right=0)
    a = (a - a.mean()) / (a.std() + 1e-9); b = (b - b.mean()) / (b.std() + 1e-9)
    xc = np.correlate(a, b, "full") / len(g)
    lag = (np.argmax(np.abs(xc)) - (len(g) - 1)) * 0.02
    return float(np.max(np.abs(xc))), float(lag)

print("computing bar + watch velocity waveforms...", flush=True)
bars = {s: bar_vel(s) for s in range(1, 6)}
watches = {s: watch_vel(s) for s in range(1, 6)}
print("\n          " + "".join(f"  vid{v:>5}" for v in range(1, 6)))
for w in range(1, 6):
    row = f"watch{w}: "
    best = (0, 0)
    for v in range(1, 6):
        r, lag = best_xcorr(watches[w][0], watches[w][1], bars[v][0], bars[v][1])
        row += f"  {r:.2f}@{lag:+.0f}s"
        if r > best[0]: best = (r, v)
    print(row + f"   -> best match VIDEO-{best[1]} (r={best[0]:.2f})", flush=True)
