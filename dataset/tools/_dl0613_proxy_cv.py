#!/usr/bin/env python3
"""One-off: CV-score the 06-13 4K120 R2 deadlifts via a 720p PROXY.

Native 4K120 is impractical to run dense/sparse-flow over directly (repeated full-res
decode per candidate pass = hours/clip). The COUNT is resolution-tolerant (the auto
candidate-gen + DetectTracker already work at 256px internally; the corpus is 440-720px),
so we pay the 4K decode ONCE to build a 1280-wide h264 proxy, run our shipped AUTO
estimator on the proxy for reps_cv, and record the TRUE 4K metadata (probed from the
master) + sha256 into the manifest. Absolute-velocity / 4K-scale scoring is a heavier
follow-up that wants native res (kept out of this count pass).
"""
from __future__ import annotations
import csv, hashlib, os, sys, time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
REPO = os.path.dirname(DATASET)
sys.path.insert(0, os.path.join(REPO, "analysis"))
import av  # noqa: E402
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.clip_store import resolve_clip  # noqa: E402

PROXY_W = 1280
PROXY_DIR = "/tmp/dl0613_proxy"
os.makedirs(PROXY_DIR, exist_ok=True)


def probe(path):
    with av.open(path) as c:
        v = c.streams.video[0]
        w, h = v.codec_context.width, v.codec_context.height
        fps = round(float(v.average_rate), 2) if v.average_rate else ""
        dur = round(float(c.duration) / 1e6, 1) if c.duration else ""
        return dict(resolution=f"{w}x{h}", fps=fps, codec=v.codec_context.name, duration_s=dur)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def transcode(src, dst, target_w=PROXY_W):
    """Decode master, spatially downscale to target_w (keep aspect+fps), re-encode h264."""
    t0 = time.time()
    with av.open(src) as ic:
        ivs = ic.streams.video[0]
        sc = target_w / ivs.codec_context.width
        ow = target_w
        oh = int(round(ivs.codec_context.height * sc)) // 2 * 2
        fps_out = int(round(float(ivs.average_rate or 30)))
        tb = Fraction(1, fps_out)
        with av.open(dst, "w") as oc:
            ovs = oc.add_stream("libx264", rate=fps_out)
            ovs.width, ovs.height, ovs.pix_fmt = ow, oh, "yuv420p"
            ovs.options = {"crf": "20", "preset": "veryfast"}
            n = 0
            for frame in ic.decode(ivs):
                rf = frame.reformat(width=ow, height=oh, format="yuv420p")
                rf.pts, rf.time_base = n, tb       # CFR pts in the output time_base
                for pkt in ovs.encode(rf):
                    oc.mux(pkt)
                n += 1
            for pkt in ovs.encode():
                oc.mux(pkt)
    print(f"    transcoded {n} frames -> {ow}x{oh} @{fps_out}fps in {time.time()-t0:.0f}s", flush=True)


def cv_count(proxy):
    cfg = VideoConfig(tracker="auto", rep_gate="relative")
    reps, meta = VideoVelocitySource(cfg).estimate(proxy, seed_bbox=None)
    mv = [r["mean_velocity"] for r in reps]
    flags = []
    if meta.get("scale_suspect"):
        flags.append("scale_suspect")
    if meta.get("static_track_suspect"):
        flags.append("static_seed")
    return dict(reps_cv=len(reps),
                mean_vel_cv=(round(sum(mv) / len(mv), 3) if mv else ""),
                cv_conf=round(meta.get("track_confidence", 0), 2),
                cv_flags="|".join(flags))


def load(path, key):
    out = {}
    if os.path.exists(path):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                k = (r.get(key) or "").strip()
                if k:
                    out[k] = r
    return out


def write(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({c: rows[k].get(c, "") for c in cols})


MAN = os.path.join(DATASET, "raw", "manifest.csv")
CLIPS = os.path.join(DATASET, "clips.csv")
MAN_COLS = ["filename", "set_id", "sha256", "bytes", "resolution", "fps", "codec",
            "duration_s", "url", "key", "note"]
CLIPS_COLS = ["clip", "lift", "load_kg", "load_unit", "gym", "equipment", "angle_kind",
              "angle_quality", "background_clutter", "occlusion", "lighting",
              "velocity_regime", "tempo_notes", "reps_cv", "reps_true", "mean_vel_cv",
              "cv_conf", "cv_flags", "has_gt", "set_id", "notes"]


def main():
    man = load(MAN, "filename")
    clips = load(CLIPS, "clip")
    targets = [fn for fn in man if "20260613-DL" in fn]
    for fn in sorted(targets):
        print(f"== {fn} ==", flush=True)
        master = resolve_clip(os.path.join("dataset", "raw", fn), REPO)
        info = probe(master)
        print(f"    master: {info['resolution']} {info['fps']}fps {info['codec']} "
              f"{os.path.getsize(master)//(1<<20)}MB", flush=True)
        sh = sha256(master)
        proxy = os.path.join(PROXY_DIR, fn.replace(".mov", ".mp4"))
        if not os.path.exists(proxy):
            transcode(master, proxy)
        cv = cv_count(proxy)
        print(f"    CV(proxy {PROXY_W}px): reps_cv={cv['reps_cv']} mean={cv['mean_vel_cv']} "
              f"conf={cv['cv_conf']} flags={cv['cv_flags']}", flush=True)
        m = man[fn]
        m.update(bytes=os.path.getsize(master), sha256=sh, **info)
        c = clips.setdefault(fn, dict.fromkeys(CLIPS_COLS, ""))
        c["reps_cv"] = cv["reps_cv"]; c["mean_vel_cv"] = cv["mean_vel_cv"]
        c["cv_conf"] = cv["cv_conf"]; c["cv_flags"] = cv["cv_flags"]
    write(MAN, MAN_COLS, man)
    write(CLIPS, CLIPS_COLS, clips)
    print("\nDONE — manifest + clips.csv updated", flush=True)


if __name__ == "__main__":
    main()
