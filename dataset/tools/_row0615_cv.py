"""CV-score the 5 06-15 barbell-row R2 videos via rotation-aware 720p proxies."""
import sys, os, csv, hashlib, time, numpy as np
from fractions import Fraction
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "analysis"))
import av, cv2
from vbt_video.frames import PyAVDecoder
from vbt_video.track import FlowTracker, auto_seed_motion
from vbt_video.kinematics import trajectory_to_reps, apply_plausibility
from vbt_video.clip_store import resolve_clip

PROXY_DIR = "/tmp/row0615_proxy"; os.makedirs(PROXY_DIR, exist_ok=True)
MAN = os.path.join(REPO, "dataset", "raw", "manifest.csv")

def probe(p):
    with av.open(p) as c:
        v = c.streams.video[0]; f = next(c.decode(v))
        return dict(resolution=f"{v.codec_context.width}x{v.codec_context.height}",
                    fps=round(float(v.average_rate), 2) if v.average_rate else "",
                    codec=v.codec_context.name,
                    duration_s=round(float(c.duration)/1e6, 1) if c.duration else "",
                    rotation=getattr(f, "rotation", 0))

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def transcode(src, dst, target_w=1280):
    with av.open(src) as ic:
        ivs = ic.streams.video[0]; fps = int(round(float(ivs.average_rate or 30))); tb = Fraction(1, fps)
        oc = ovs = ow = oh = None; n = 0
        for fr in ic.decode(ivs):
            img = PyAVDecoder._apply_rotation(fr.to_ndarray(format="bgr24"), fr.rotation)
            if oc is None:
                h0, w0 = img.shape[:2]; ow = (target_w if w0 > target_w else w0)//2*2
                oh = int(round(h0*ow/w0))//2*2
                oc = av.open(dst, "w"); ovs = oc.add_stream("libx264", rate=fps)
                ovs.width, ovs.height, ovs.pix_fmt = ow, oh, "yuv420p"; ovs.options = {"crf":"20","preset":"veryfast"}
            of = av.VideoFrame.from_ndarray(cv2.resize(img, (ow, oh)), format="bgr24")
            of.pts, of.time_base = n, tb
            for pkt in ovs.encode(of): oc.mux(pkt)
            n += 1
        for pkt in ovs.encode(): oc.mux(pkt)
        oc.close()
    return ow, oh, n

def vit_n(sid):
    return len({r['true_rep'] for r in csv.DictReader(open(os.path.join(REPO,'dataset/rep_metrics.csv')))
                if r['set_id']==sid and r['vendor']=='vitruve' and r['metric']=='mean_velocity'})

man = {r['filename']: r for r in csv.DictReader(open(MAN))}
man_cols = list(next(iter(man.values())).keys())
for s in range(1, 6):
    fn = f"20260615-ROW-{s}.mov"; sid = f"20260615-ROW-{s}"
    print(f"== {fn} ==", flush=True)
    local = resolve_clip(os.path.join("dataset", "raw", fn), REPO)
    info = probe(local)
    print(f"   master {info['resolution']} {info['fps']}fps {info['codec']} rot={info['rotation']} "
          f"{os.path.getsize(local)//(1<<20)}MB", flush=True)
    proxy = os.path.join(PROXY_DIR, fn.replace(".mov", ".mp4"))
    if not os.path.exists(proxy):
        t0 = time.time(); ow, oh, n = transcode(local, proxy)
        print(f"   proxy {ow}x{oh} {n}f in {time.time()-t0:.0f}s", flush=True)
    src = PyAVDecoder(proxy); fl = FlowTracker().track(src, auto_seed_motion(src))
    reps = apply_plausibility([dict(r) for r in trajectory_to_reps(fl.traj, 1.0, 0.12, 0.25, rep_gate="relative")])
    gt = vit_n(sid)
    print(f"   CV(auto-seed) reps={len(reps)} GT={gt} yspan={np.ptp(fl.traj[:,2]):.0f}px conf={fl.confidence:.2f}", flush=True)
    m = man[fn]; m.update(bytes=os.path.getsize(local), sha256=sha(local),
                          resolution=info['resolution'], fps=info['fps'], codec=info['codec'],
                          duration_s=info['duration_s'])
with open(MAN, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=man_cols); w.writeheader()
    for fn in sorted(man): w.writerow(man[fn])
print("DONE", flush=True)
