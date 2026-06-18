#!/usr/bin/env python3
"""Compress 4K/120fps masters → an upright ~720p proxy so they join the CV corpus.

Native 4K/high-fps is impractical to flow over directly (full-res decode per candidate pass =
hours/clip, learning #20). The rep COUNT is resolution-tolerant (the auto candidate-gen +
trackers work at ~256px internally), so we pay the 4K decode ONCE to build a 720-wide H.264
proxy, then run the shipped seed-free AUTO estimator on the proxy. Generalizes the one-off
`_dl0613_proxy_cv.py` to any clip the coverage check flags as 4K (default: all manifest clips
≥1440p that have GT and aren't yet scoreable locally).

Proxies are cached at `dataset/raw/<set_id>_proxy.mp4` (gitignored, regenerable). Register the
proxy in `cv_eval.CLIPS` to make the clip a live board member (720p scores at board speed).

    python dataset/tools/transcode_proxy.py                 # all 4K manifest clips
    python dataset/tools/transcode_proxy.py 20260613-DL-1   # specific set_ids
"""
from __future__ import annotations
import csv, os, sys, time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
REPO = os.path.dirname(DATASET)
sys.path.insert(0, os.path.join(REPO, "analysis"))
import av  # noqa: E402
import cv2  # noqa: E402
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.frames import PyAVDecoder  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402

PROXY_W = 720
MAN = os.path.join(DATASET, "raw", "manifest.csv")


def transcode(src, dst, target_w=PROXY_W):
    """Decode master UPRIGHT (honour frame.rotation), downscale to target_w, re-encode H.264.
    Upright matters: a portrait master decoded raw moves the bar along image-X and the Y-axis
    rep segmenter sees a static track (learning #22)."""
    t0 = time.time()
    with av.open(src) as ic:
        ivs = ic.streams.video[0]
        fps_out = int(round(float(ivs.average_rate or 30)))
        # cap proxy fps so a 120fps master doesn't make a giant proxy (rep cadence is ~Hz)
        fps_out = min(fps_out, 60)
        tb = Fraction(1, fps_out)
        oc = ow = oh = ovs = None
        n = 0
        for frame in ic.decode(ivs):
            img = PyAVDecoder._apply_rotation(frame.to_ndarray(format="bgr24"), frame.rotation)
            if oc is None:
                h0, w0 = img.shape[:2]
                ow = (target_w if w0 > target_w else w0) // 2 * 2
                oh = int(round(h0 * ow / w0)) // 2 * 2
                oc = av.open(dst, "w")
                ovs = oc.add_stream("libx264", rate=fps_out)
                ovs.width, ovs.height, ovs.pix_fmt = ow, oh, "yuv420p"
                ovs.options = {"crf": "20", "preset": "veryfast"}
            of = av.VideoFrame.from_ndarray(cv2.resize(img, (ow, oh)), format="bgr24")
            of.pts, of.time_base = n, tb
            for pkt in ovs.encode(of):
                oc.mux(pkt)
            n += 1
        for pkt in ovs.encode():
            oc.mux(pkt)
        oc.close()
    print(f"    transcoded {n} frames -> {ow}x{oh} @{fps_out}fps in {time.time()-t0:.0f}s "
          f"({os.path.getsize(dst)//(1<<20)}MB)", flush=True)


def is_4k(res):
    try:
        w, h = (int(x) for x in res.lower().split("x"))
        return max(w, h) >= 2560
    except Exception:
        return False


def main():
    want = set(sys.argv[1:])
    man = {r["set_id"]: r for r in csv.DictReader(open(MAN))}
    targets = [s for s, r in man.items() if (want and s in want) or (not want and is_4k(r.get("resolution", "")))]
    if not targets:
        print("no 4K targets"); return
    print(f"{'set_id':<16}{'master':<22}{'proxy reps (seed-free AUTO)'}")
    for sid in sorted(targets):
        r = man[sid]
        master = resolve_clip(os.path.join("dataset", "raw", r["filename"]), REPO)
        proxy = os.path.join(DATASET, "raw", f"{sid}_proxy.mp4")
        if not os.path.exists(proxy):
            transcode(master, proxy)
        reps, meta = VideoVelocitySource(VideoConfig(tracker="auto", rep_gate="relative")).estimate(proxy)
        print(f"{sid:<16}{r.get('resolution',''):<10} {r.get('fps',''):>6}fps   "
              f"reps={len(reps)}  conf={meta.get('track_confidence',0):.2f}  "
              f"pick={meta.get('auto_pick','?')} honest={meta.get('track_honest','?')}", flush=True)


if __name__ == "__main__":
    main()
