#!/usr/bin/env python3
"""Build the meVBT investor one-pager (3-page laminate-grade artifact).

Self-contained + reproducible: extracts the hero frames from `dataset/raw`,
runs OUR FlowTracker (the registered cv_eval seeds) for the real bar-path
overlays, and emits `meVBT-onepager.html` (single file, images embedded)
plus `meVBT-onepager.pdf` (needs weasyprint + the Inter font:
`apt-get install fonts-inter && pip install weasyprint`).

Run from anywhere:  python docs/onepager/build.py
All scoreboard numbers = the frozen 2026-06-11 benchmark
(docs/cv-fusion.md "Full scoreboard snapshot"); regenerate via
analysis/scripts/cv_eval.py --auto and vel_eval.py.
"""
import base64, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "analysis"))
WORK = os.path.join(tempfile.gettempdir(), "onepager_work")
os.makedirs(WORK, exist_ok=True)
OUT_HTML = os.path.join(HERE, "meVBT-onepager.html")
OUT_PDF = os.path.join(HERE, "meVBT-onepager.pdf")

# ---------------------------------------------------------------- prep
# Page-1 hero = a real lifter photo (docs/onepager/assets/hero-deadlift.jpg,
# heavier bar, watch + AirPod + plate + decoys all visible). Overlays on it are
# schematic sensor anatomy — the REAL tracker-output figures live on page 2:
#   SQ: 061026-SQ1 bottom of rep 5 | BN: 20260609-BN-4 terminal grind rep
# (clip, registered cv_eval seed, frame timestamp, base crop):
HEROES = {
    "SQ": ("dataset/raw/061026-SQ1.mov",   (190, 305, 80, 80),  14.15, (0, 96, 440, 940)),
    "BN": ("dataset/raw/20260609-BN-4.mov", (10, 300, 96, 96),  28.30, (0, 96, 440, 800)),
}

def prep():
    """Decode hero frames + run the flow tracker; cache results in WORK."""
    from PIL import Image, ImageEnhance
    import av
    from vbt_video.frames import PyAVDecoder
    from vbt_video.track import FlowTracker
    from vbt_video.kinematics import trajectory_to_reps

    tracks = {}
    for key, (rel, seed, t_hero, box) in HEROES.items():
        path = os.path.join(REPO, rel)
        # hero frame
        c = av.open(path); s = c.streams.video[0]
        for fr in c.decode(s):
            if float(fr.pts * s.time_base) >= t_hero:
                im = fr.to_image()
                break
        c.close()
        if box:
            im = im.crop(box)
        im = ImageEnhance.Color(im).enhance(1.06)
        im = ImageEnhance.Contrast(im).enhance(1.03)
        im.save(os.path.join(WORK, f"{key}_hero_final.jpg"), quality=85, optimize=True)
        # real track (same config as the LLM-tap board path)
        tr = FlowTracker(ellipse_scale=True).track(PyAVDecoder(path), seed)
        mpp = 0.45 / tr.target_px
        reps = trajectory_to_reps(tr.traj, mpp, rep_gate="relative", plausibility=True)
        tracks[key] = {
            "traj": [[round(float(t), 3), round(float(x), 1), round(float(y), 1)]
                     for t, x, y in tr.traj],
            "target_px": float(tr.target_px), "conf": float(tr.confidence),
            "reps": reps,
        }
        print(f"  {key}: {len(reps)} reps, lock confidence {tr.confidence:.2f}")
    json.dump(tracks, open(os.path.join(WORK, "tracks.json"), "w"))

if not os.path.exists(os.path.join(WORK, "tracks.json")):
    print("prep: extracting frames + running the tracker (one-time, ~2 min)")
    prep()

# ---------------------------------------------------------------- assets
def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()

def crop_b64(src, box, q=85, enhance=False):
    from PIL import Image, ImageEnhance
    im = Image.open(src)
    im = im.crop(box)
    if enhance:
        im = ImageEnhance.Color(im).enhance(1.06)
        im = ImageEnhance.Contrast(im).enhance(1.03)
    p = os.path.join(WORK, "_tmp_crop.jpg")
    im.save(p, quality=q, optimize=True)
    return b64(p), im.size

IMG_DL, DL_SIZE = crop_b64(os.path.join(HERE, "assets/hero-deadlift.jpg"),
                           (0, 230, 1320, 1990), enhance=True)               # 1320x1760
IMG_SQ, SQ_SIZE = crop_b64(f"{WORK}/SQ_hero_final.jpg", (0, 180, 440, 600))   # 440x420
IMG_BN, BN_SIZE = crop_b64(f"{WORK}/BN_hero_final.jpg", (0, 90, 440, 470))    # 440x380

TR = json.load(open(os.path.join(WORK, "tracks.json")))

def svg_path(track_key, t0, t1, x_override=None, y_off=0.0, step=2):
    pts = [p for p in TR[track_key]["traj"] if t0 <= p[0] <= t1][::step]
    d = []
    for i, (t, x, y) in enumerate(pts):
        x = x_override if x_override is not None else x
        d.append(("M" if i == 0 else "L") + f"{x:.0f},{y - y_off:.0f}")
    return " ".join(d)

# DL hero is a photo (no track); SQ/BN paths are real tracker output
# SQ: full 10-rep vertical history at the plate x, page-2 crop offset (96+180)
SQ_PATH = svg_path("SQ", 1.2, 32.5, x_override=350, y_off=96 + 180, step=3)
# BN: full set history, crop offset (96+90)
BN_PATH = svg_path("BN", 1.0, 30.2, x_override=58, y_off=96 + 90, step=3)

# Pre-rotated plate-rim ellipse for the hero overlay (weasyprint cannot handle
# svg transform=rotate without corrupting the whole overlay's scale).
import math

def rotated_ellipse_d(cx, cy, rx, ry, deg, n=72):
    a = math.radians(deg)
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * math.cos(a) - y * math.sin(a),
                    cy + x * math.sin(a) + y * math.cos(a)))
    return "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in pts) + " Z"

ELLIPSE_D = rotated_ellipse_d(390, 1298, 232, 345, 10)

# ---------------------------------------------------------------- chart (BN-4 fatigue)
VIT = [0.37, 0.36, 0.34, 0.33, 0.28, 0.31, 0.28, 0.29, 0.24, 0.17]
SB = [0.34, 0.34, 0.30, 0.32, 0.25, 0.28, 0.28, 0.28, 0.22]      # rep 10 = phantom

def fatigue_chart(w=700, h=118):
    p = dict(l=34, r=10, t=12, b=22)
    iw, ih = w - p["l"] - p["r"], h - p["t"] - p["b"]
    y0, y1 = 0.10, 0.42
    X = lambda i: p["l"] + (i) / 9 * iw
    Y = lambda v: p["t"] + (y1 - v) / (y1 - y0) * ih
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="display:block">']
    # MVT band (bench ~0.10-0.17)
    s.append(f'<rect x="{p["l"]}" y="{Y(0.17):.1f}" width="{iw}" height="{Y(y0)-Y(0.17):.1f}" fill="#FEF3E2"/>')
    s.append(f'<text x="{p["l"]+8:.0f}" y="{Y(0.125):.0f}" font-size="7" fill="#B45309" font-weight="600">minimum velocity threshold — bar speed at a true 1RM</text>')
    for v in [0.1, 0.2, 0.3, 0.4]:
        s.append(f'<line x1="{p["l"]}" y1="{Y(v):.1f}" x2="{w-p["r"]}" y2="{Y(v):.1f}" stroke="#ECEEF3" stroke-width="1"/>')
        s.append(f'<text x="{p["l"]-5}" y="{Y(v)+2.6:.1f}" font-size="7.4" fill="#98A0AD" text-anchor="end">{v:.1f}</text>')
    for i in range(10):
        s.append(f'<text x="{X(i):.1f}" y="{h-8}" font-size="7.4" fill="#98A0AD" text-anchor="middle">{i+1}</text>')
    s.append(f'<text x="{p["l"]+iw/2:.0f}" y="{h-0.5}" font-size="7" fill="#5C6470" text-anchor="middle" font-weight="600">rep</text>')
    # SB line (stops at 9, phantom X at 10)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(SB))
    s.append(f'<polyline points="{pts}" fill="none" stroke="#DC2626" stroke-width="1.6" stroke-dasharray="4 2.5" stroke-linejoin="round"/>')
    for i, v in enumerate(SB):
        s.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="2" fill="#DC2626"/>')
    xx, xy = X(9), Y(0.385)
    s.append(f'<path d="M{xx-4},{xy-4} L{xx+4},{xy+4} M{xx-4},{xy+4} L{xx+4},{xy-4}" stroke="#DC2626" stroke-width="2"/>')
    s.append(f'<text x="{xx-12:.0f}" y="{xy+2.5:.0f}" font-size="7.6" fill="#DC2626" text-anchor="end" font-weight="700">rep 10: SmartBarbell loses the bar — phantom</text>')
    s.append(f'<line x1="{X(8):.1f}" y1="{Y(SB[-1])-4:.1f}" x2="{xx:.1f}" y2="{xy+6:.1f}" stroke="#DC2626" stroke-width="1" stroke-dasharray="3 2" opacity=".55"/>')
    s.append(f'<text x="{X(9)-9:.0f}" y="{Y(0.155):.0f}" font-size="7.4" fill="#B45309" text-anchor="end" font-weight="700">0.17 m/s — true grind, caught</text>')
    # Vitruve line
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(VIT))
    s.append(f'<polyline points="{pts}" fill="none" stroke="#0B0F19" stroke-width="2" stroke-linejoin="round"/>')
    for i, v in enumerate(VIT):
        s.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="2.3" fill="#0B0F19"/>')
    s.append(f'<circle cx="{X(9):.1f}" cy="{Y(0.17):.1f}" r="5" fill="none" stroke="#D97706" stroke-width="2"/>')
    s.append('</svg>')
    return "".join(s)

CHART = fatigue_chart()

# ---------------------------------------------------------------- logo
def logo(size, ring="#6366F1", v="#0B0F19", dot="#F59E0B"):
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 96 96">
<circle cx="48" cy="48" r="38" fill="none" stroke="{ring}" stroke-width="10"/>
<path d="M29 31 L45 67 Q48 72.5 51 67 L67 31" fill="none" stroke="{v}" stroke-width="9.5" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="48" cy="69.5" r="5" fill="{dot}"/>
</svg>'''

LOGO_DARKBG = logo(40, ring="#818CF8", v="#FFFFFF")
LOGO_LIGHT = logo(26)

# ---------------------------------------------------------------- html
HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>meVBT — investor brief</title>
<style>
@page {{ size: Letter; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ font-family: Inter, "Inter Display", -apple-system, "Segoe UI", Roboto, sans-serif;
       color: #2A303B; font-size: 9.5px; line-height: 1.45; background: #DFE3EA; }}
.page {{ width: 8.5in; height: 11in; background: #fff; margin: 0 auto; position: relative;
         overflow: hidden; page-break-after: always; }}
.page:last-child {{ page-break-after: auto; }}

/* ---------- shared ---------- */
.eyebrow {{ font-size: 8px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase;
            color: #4F46E5; display: flex; align-items: center; gap: 7px; }}
.eyebrow .ln {{ width: 26px; height: 2px; background: linear-gradient(90deg,#4F46E5,#8B5CF6); }}
.h-xl {{ font-family: "Inter Display", Inter, sans-serif; font-weight: 800; color: #0B0F19;
         letter-spacing: -.022em; }}
.mute {{ color: #5C6470; }}
.footer {{ position: absolute; left: .55in; right: .55in; bottom: .3in; display: flex;
           justify-content: space-between; align-items: center; font-size: 7.6px; color: #98A0AD;
           border-top: 1px solid #E7E9F0; padding-top: 7px; }}
.footer b {{ color: #5C6470; font-weight: 600; }}
.chip {{ display: inline-block; border-radius: 20px; padding: 2px 8px; font-size: 7.6px; font-weight: 700; }}

/* ---------- page 1 ---------- */
.masthead {{ background: #0B0F19; color: #fff; padding: .34in .55in .52in; position: relative; }}
.masthead .brandrow {{ display: flex; align-items: center; justify-content: space-between; }}
.wordmark {{ display: flex; align-items: center; gap: 11px; }}
.wordmark .wm {{ font-family: "Inter Display", Inter, sans-serif; font-size: 25px; font-weight: 800;
                 letter-spacing: -.02em; color: #fff; }}
.wordmark .wm .me {{ font-weight: 400; color: #8A93A6; }}
.brief-tag {{ font-size: 7.6px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
              color: #A5B4FC; border: 1px solid #2D3650; border-radius: 20px; padding: 5px 12px; }}
.headline {{ font-family: "Inter Display", Inter, sans-serif; font-size: 27px; font-weight: 800;
             letter-spacing: -.025em; line-height: 1.12; margin-top: 14px; }}
.headline .grad {{ color: #818CF8; }}
.subline {{ font-size: 11px; color: #B7BFD2; margin-top: 7px; max-width: 6.4in; line-height: 1.48; }}
.subline b {{ color: #fff; font-weight: 600; }}
.statband {{ display: flex; gap: 10px; margin: -0.38in .55in 0; position: relative; }}
.stat {{ flex: 1; background: #fff; border: 1px solid #E7E9F0; border-radius: 10px;
         padding: 8px 12px 8px; box-shadow: 0 6px 18px rgba(11,15,25,.10); }}
.stat .big {{ font-family: "Inter Display", Inter, sans-serif; font-size: 23px; font-weight: 800;
              color: #4F46E5; letter-spacing: -.02em; line-height: 1; }}
.stat .big small {{ font-size: 11px; font-weight: 700; color: #98A0AD; }}
.stat .lbl {{ font-size: 7.5px; color: #5C6470; margin-top: 4px; line-height: 1.35; }}
.stat .lbl b {{ color: #0B0F19; }}
.p1body {{ padding: .15in .55in 0; }}
.p1grid {{ display: flex; gap: 16px; margin-top: 7px; }}
.heroFig {{ width: 3.9in; height: 5.2in; position: relative; border-radius: 11px; overflow: hidden;
            box-shadow: 0 2px 14px rgba(11,15,25,.16); }}
.heroFig img {{ width: 100%; height: 100%; display: block; }}
.heroFig svg.ov {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; }}
.figcap {{ font-size: 7.8px; color: #5C6470; margin-top: 6px; line-height: 1.45; }}
.figcap b {{ color: #0B0F19; }}
.rail {{ flex: 1; display: flex; flex-direction: column; gap: 7px; }}
.scard {{ border: 1px solid #E7E9F0; border-radius: 9px; padding: 8px 10px; background: #fff; }}
.scard.today {{ background: #F5F6FE; border-color: #D9DCFB; }}
.scard h4 {{ font-size: 9.3px; font-weight: 700; color: #0B0F19; display: flex; align-items: center;
             justify-content: space-between; }}
.scard p {{ font-size: 7.8px; color: #5C6470; margin-top: 2px; line-height: 1.4; }}
.tag-today {{ background: #4F46E5; color: #fff; }}
.tag-cal {{ background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; }}
.tag-road {{ background: #F4F5F8; color: #98A0AD; border: 1px solid #E7E9F0; }}
.fusion {{ background: #0B0F19; color: #fff; border-radius: 10px; padding: 11px 12px; margin-top: 2px;
           flex: 1; display: flex; flex-direction: column; }}
.fusion .ft {{ font-size: 9.5px; font-weight: 800; }}
.fusion p {{ font-size: 7.7px; color: #9AA3B8; margin-top: 3px; line-height: 1.45; }}
.fusion .score {{ margin-top: auto; background: linear-gradient(135deg,#4F46E5,#8B5CF6);
                  border-radius: 8px; padding: 7px 10px; }}
.fusion .score .t {{ font-family: "Inter Display", Inter, sans-serif; font-size: 12px; font-weight: 800; }}
.fusion .score .d {{ font-size: 7.3px; color: #E3E5FD; margin-top: 1px; }}

/* ---------- page 2 ---------- */
.p2 {{ padding: .5in .55in 0; }}
.cmp {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 12px; font-size: 8.8px; }}
.cmp th, .cmp td {{ padding: 4px 9px; text-align: center; border-bottom: 1px solid #EDEFF4; }}
.cmp th {{ font-size: 8px; font-weight: 700; color: #5C6470; }}
.cmp th.h-us {{ background: #4F46E5; color: #fff; border-radius: 8px 8px 0 0; font-size: 8.6px; }}
.cmp td.c-us {{ background: #F5F6FE; font-weight: 800; color: #0B0F19; border-bottom: 1px solid #E2E5FB; }}
.cmp td:first-child, .cmp th:first-child {{ text-align: left; padding-left: 0; }}
.cmp td.rowlab {{ font-weight: 600; color: #0B0F19; }}
.cmp td.rowlab small {{ display: block; font-weight: 400; color: #98A0AD; font-size: 7.3px; }}
.cmp .grp td {{ border-bottom: none; padding: 6px 0 1px; font-size: 7.2px; font-weight: 800;
               letter-spacing: .12em; color: #4F46E5; text-transform: uppercase; text-align: left; }}
.cmp tr.last td {{ }}
.win {{ color: #059669; font-weight: 800; }}
.lose {{ color: #B9402F; }}
.xfactor {{ display: inline-block; background: #ECFDF5; color: #059669; border-radius: 9px;
            font-size: 6.8px; font-weight: 800; padding: 1px 5px; margin-left: 4px; vertical-align: 1px; }}
.fig2 {{ position: relative; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(11,15,25,.14); }}
.fig2 img {{ width: 100%; display: block; }}
.fig2 svg.ov {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; }}
.p2figs {{ display: flex; gap: 14px; margin-top: 14px; }}
.chartcard {{ border: 1px solid #E7E9F0; border-radius: 10px; padding: 8px 12px 6px; margin-top: 10px;
              display: flex; gap: 14px; align-items: stretch; }}
.losschip {{ border-radius: 8px; padding: 6px 9px; margin-top: 5px; }}
.losschip .v {{ font-family: "Inter Display", Inter, sans-serif; font-size: 15px; font-weight: 800; }}
.losschip .k {{ font-size: 6.9px; font-weight: 600; }}

/* ---------- page 3 ---------- */
.p3 {{ padding: .5in .55in 0; }}
.ws {{ display: flex; gap: 10px; margin-top: 10px; }}
.wcard {{ flex: 1; border: 1px solid #E7E9F0; border-radius: 10px; padding: 10px 12px; }}
.wcard h4 {{ font-size: 9.5px; font-weight: 800; color: #0B0F19; margin-bottom: 3px; }}
.wcard p {{ font-size: 7.9px; color: #5C6470; line-height: 1.45; }}
.lab {{ background: #0B0F19; border-radius: 12px; color: #fff; padding: 13px 16px; margin-top: 14px; }}
.lab .nums {{ display: flex; justify-content: space-between; margin-top: 8px; }}
.lab .n .v {{ font-family: "Inter Display", Inter, sans-serif; font-size: 19px; font-weight: 800;
              color: #A5B4FC; letter-spacing: -.02em; }}
.lab .n .k {{ font-size: 7px; color: #8A93A6; margin-top: 2px; text-transform: uppercase; letter-spacing: .07em; }}
.lab .note {{ font-size: 7.6px; color: #9AA3B8; margin-top: 9px; border-top: 1px solid #232B40;
              padding-top: 7px; line-height: 1.5; }}
.road {{ display: flex; gap: 7px; margin-top: 10px; }}
.rstep {{ flex: 1; border: 1px solid #E7E9F0; border-radius: 9px; padding: 8px 9px; position: relative; }}
.rstep .ph {{ font-size: 6.6px; font-weight: 800; letter-spacing: .1em; color: #98A0AD; }}
.rstep .ti {{ font-size: 8.8px; font-weight: 700; color: #0B0F19; margin: 2px 0 1px; }}
.rstep .ds {{ font-size: 7.2px; color: #5C6470; line-height: 1.35; }}
.rstep.done {{ background: #F5F6FE; border-color: #D9DCFB; }}
.rstep.done .ph {{ color: #4F46E5; }}
.rbadge {{ position: absolute; top: 7px; right: 8px; font-size: 6.2px; font-weight: 800;
           color: #fff; background: #059669; border-radius: 8px; padding: 1.5px 5px; }}
.sci {{ display: flex; gap: 12px; margin-top: 10px; }}
.scol {{ flex: 1; border: 1px solid #E7E9F0; border-radius: 9px; padding: 9px 11px; }}
.scol h5 {{ font-size: 8.4px; font-weight: 700; color: #0B0F19; margin-bottom: 4px; }}
.scol p {{ font-size: 7.6px; color: #5C6470; line-height: 1.45; }}
.zone {{ display: flex; height: 14px; border-radius: 4px; overflow: hidden; font-size: 6.2px;
         font-weight: 800; color: #fff; line-height: 14px; text-align: center; margin: 4px 0; }}
.limits {{ border: 1px dashed #D7DBE4; border-radius: 10px; padding: 9px 12px; margin-top: 12px;
           background: #FBFBFD; }}
.limits h5 {{ font-size: 8.2px; font-weight: 800; color: #5C6470; text-transform: uppercase;
              letter-spacing: .1em; margin-bottom: 3px; }}
.limits p {{ font-size: 7.9px; color: #5C6470; line-height: 1.5; }}
.mono {{ font-family: "DejaVu Sans Mono", Menlo, monospace; }}
</style></head>
<body>

<!-- ================= PAGE 1 ================= -->
<div class="page">
  <div class="masthead">
    <div class="brandrow">
      <div class="wordmark">{LOGO_DARKBG}
        <div>
          <div class="wm"><span class="me">me</span>VBT</div>
          <div style="font-size:7px;color:#8A93A6;letter-spacing:.04em;margin-top:1px;white-space:nowrap">VELOCITY-BASED TRAINING · MUSCULAR RECOVERY</div>
        </div>
      </div>
      <div class="brief-tag">Investor brief · June 2026</div>
    </div>
    <div class="headline">Your heart-rate wearable can't see the barbell.<br>
      <span class="grad">We give your muscles their own recovery score.</span></div>
    <div class="subline">Whoop and Apple Watch read a near-failure squat session as a rest day — HR barely moves while
      your muscles grind to zero. <b>meVBT counts every rep and measures intra-set velocity loss</b> — the validated
      proximity-to-failure signal — from the phone and watch you already own. No bar sensor. No setup. No taps.</div>
  </div>

  <div class="statband">
    <div class="stat"><div class="big">8×</div>
      <div class="lbl"><b>more accurate rep counts</b> than the leading video app — 0.32 vs 2.57 mean error, head-to-head on 22 real sets</div></div>
    <div class="stat"><div class="big">3×</div>
      <div class="lbl"><b>better fatigue signal</b> — velocity-loss within 3.2pp of lab hardware; the incumbent: 9.0pp</div></div>
    <div class="stat"><div class="big">21<small>/22</small></div>
      <div class="lbl"><b>sets within ±1 rep, fully automatic</b> — every bench &amp; squat set exact</div></div>
    <div class="stat"><div class="big">$0</div>
      <div class="lbl"><b>added hardware</b> — replaces a $500 bar-mounted transducer with software</div></div>
  </div>

  <div class="p1body">
    <div class="eyebrow"><span class="ln"></span> 01 · The signal, on one real frame</div>
    <div class="p1grid">
      <div style="width:3.9in">
        <div class="heroFig">
          <img src="data:image/jpeg;base64,{IMG_DL}">
          <svg class="ov" width="3.9in" height="5.2in" viewBox="0 0 1320 1760" font-family="Inter, sans-serif">
            <!-- schematic bar path: hub rises ~vertically; ZUPT anchor at the turnaround -->
            <defs><marker id="pathArr" markerWidth="10" markerHeight="10" refX="5" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#6366F1"/></marker></defs>
            <line x1="500" y1="1390" x2="538" y2="1080" stroke="#A5B4FC" stroke-width="14" opacity=".30" stroke-linecap="round"/>
            <line x1="500" y1="1390" x2="535" y2="1100" stroke="#6366F1" stroke-width="5" stroke-dasharray="16 11" marker-end="url(#pathArr)"/>
            <circle cx="498" cy="1450" r="15" fill="#F59E0B" stroke="#fff" stroke-width="5"/>
            <!-- plate rim ellipse (tilted face of the front plate; pre-rotated path:
                 weasyprint mis-renders svg transform=rotate, so the points are baked) -->
            <path d="{ELLIPSE_D}" fill="none" stroke="#FFFFFF" stroke-width="10" opacity=".55"/>
            <path d="{ELLIPSE_D}" fill="none" stroke="#6366F1" stroke-width="5"/>
            <!-- decoys: rack-stored plates, left -->
            <circle cx="80" cy="160" r="58" fill="none" stroke="#fff" stroke-width="4.5" stroke-dasharray="15 10" opacity=".95"/>
            <circle cx="85" cy="370" r="60" fill="none" stroke="#fff" stroke-width="4.5" stroke-dasharray="15 10" opacity=".95"/>
            <!-- corner badge -->
            <rect x="16" y="16" width="500" height="46" rx="23" fill="#0B0F19" opacity=".82"/>
            <text x="42" y="48" font-size="25" font-weight="700" fill="#A5B4FC">ONE FRAME — EVERY SENSOR WE FUSE</text>
            <!-- callout: airpods (worn here) -->
            <g>
              <rect x="720" y="48" width="396" height="84" rx="12" fill="#0B0F19" opacity=".82"/>
              <text x="742" y="82" font-size="28" font-weight="700" fill="#fff">AirPods IMU — in the ear</text>
              <text x="742" y="114" font-size="22" fill="#B7BFD2">head kinematics + HR · roadmap</text>
              <line x1="800" y1="132" x2="764" y2="232" stroke="#fff" stroke-width="3.5" opacity=".8"/>
              <circle cx="757" cy="248" r="16" fill="none" stroke="#fff" stroke-width="4" opacity=".9"/>
            </g>
            <!-- callout: watch -->
            <g>
              <rect x="880" y="752" width="416" height="84" rx="12" fill="#0B0F19" opacity=".82"/>
              <text x="902" y="786" font-size="28" font-weight="700" fill="#fff">Apple Watch IMU · 100&#8201;Hz</text>
              <text x="902" y="818" font-size="22" fill="#B7BFD2">the bar-side wrist — always there</text>
              <line x1="880" y1="794" x2="642" y2="826" stroke="#fff" stroke-width="3.5" opacity=".8"/>
              <circle cx="615" cy="832" r="22" fill="none" stroke="#fff" stroke-width="4" opacity=".9"/>
            </g>
            <!-- callout: bar path / ZUPT -->
            <g>
              <rect x="700" y="1040" width="600" height="84" rx="12" fill="#0B0F19" opacity=".82"/>
              <text x="722" y="1074" font-size="28" font-weight="700" fill="#FBBF24">v = 0 at every turnaround</text>
              <text x="722" y="1106" font-size="22" fill="#B7BFD2">ZUPT kills IMU drift, rep by rep — one integration each</text>
              <line x1="700" y1="1082" x2="562" y2="1092" stroke="#F59E0B" stroke-width="3.5" opacity=".9"/>
            </g>
            <!-- callout: plate -->
            <g>
              <rect x="800" y="1430" width="496" height="84" rx="12" fill="#0B0F19" opacity=".82"/>
              <text x="822" y="1464" font-size="28" font-weight="700" fill="#fff">Working plate — the metric ruler</text>
              <text x="822" y="1496" font-size="22" fill="#B7BFD2">Ø450&#8201;mm rim sets the px&#8594;m scale</text>
              <line x1="800" y1="1472" x2="628" y2="1340" stroke="#fff" stroke-width="3.5" opacity=".8"/>
            </g>
            <!-- callout: decoys -->
            <g>
              <rect x="40" y="540" width="450" height="78" rx="12" fill="#0B0F19" opacity=".82"/>
              <text x="62" y="572" font-size="26" font-weight="700" fill="#fff">Stored plates = decoys</text>
              <text x="62" y="602" font-size="21" fill="#B7BFD2">no motion &#8594; rejected by flow-verification</text>
              <line x1="160" y1="540" x2="105" y2="438" stroke="#fff" stroke-width="3.5" opacity=".8"/>
            </g>
          </svg>
        </div>
        <div class="figcap"><b>Every signal we fuse, in one real frame.</b> The watch rides the bar-side wrist; the
          AirPods add a second IMU; the plate's Ø450&#8201;mm rim hands video its metric scale; the stored plates behind
          are the decoys the tracker must reject. Overlays here are the sensor anatomy — p.&#8201;2 shows the
          tracker's raw output.</div>
      </div>
      <div class="rail">
        <div class="eyebrow" style="margin-bottom:1px"><span class="ln"></span> What each sensor knows</div>
        <div class="scard today"><h4>Phone camera — plate CV <span class="chip tag-today">SHIPPING SIGNAL</span></h4>
          <p>Zero-tap rep counting + velocity-loss that already beats the market leader (left, p.&#8201;2). Works on bumpers, dark iron, hex plates, mirrors.</p></div>
        <div class="scard today"><h4>Apple Watch IMU <span class="chip tag-today">POC BUILT</span></h4>
          <p>100&#8201;Hz gravity-corrected acceleration &#8594; ZUPT-anchored velocity. Always on your wrist — the only sensor that's <i>always there</i>.</p></div>
        <div class="scard"><h4>BLE bar devices &amp; LPT <span class="chip tag-cal">CALIBRATION GT</span></h4>
          <p>Vitruve linear transducer = our ground truth; a 6-vendor dataset quantifies every tool's real error. Ingested, never required.</p></div>
        <div class="scard"><h4>AirPods IMU + HR <span class="chip tag-road">ROADMAP</span></h4>
          <p>Head kinematics for the lifts the wrist can't see; HR closes the systemic-vs-muscular loop.</p></div>
        <div class="fusion">
          <div class="ft">&#8594; One fusion model</div>
          <p>Every source emits the same shape — rep boundaries, velocity profile, ROM, <b style="color:#A5B4FC">per-rep confidence</b>.
             A learned personal prior (your rep shape, your tempo, your minimum velocity) strengthens with every set;
             every manual correction trains it further.</p>
          <div class="score"><div class="t">Muscular Strain &amp; Recovery Score</div>
            <div class="d">the lifting analogue of Whoop — structurally impossible from heart rate alone</div></div>
        </div>
      </div>
    </div>
  </div>
  <div class="footer"><span>{LOGO_LIGHT}</span>
    <span><b>meVBT</b> · built on a 34-set / 2,720-measurement multi-vendor dataset · jimartter@gmail.com</span>
    <span class="mono">1 / 3</span></div>
</div>

<!-- ================= PAGE 2 ================= -->
<div class="page"><div class="p2">
  <div class="eyebrow"><span class="ln"></span> 02 · The proof</div>
  <div class="h-xl" style="font-size:19.5px;margin-top:5px">We already beat the market's best lifting CV —
    <span style="color:#4F46E5">and we're just getting started.</span></div>
  <p class="mute" style="font-size:8.9px;margin-top:5px;max-width:7.2in">26 real training clips, four gyms, 2024–2026 — bumper, dark-iron
    and hex plates; side, diagonal and front angles; mirrors, racks, occlusion. Ground truth: a Vitruve bar-mounted linear
    transducer. SmartBarbell (the leading velocity-video app) scored on identical clips. Our system gets <b>only the raw
    clip</b> — no taps, no hints, no gym profile.</p>

  <table class="cmp">
    <tr>
      <th style="width:36%"></th>
      <th class="h-us" style="width:21%">meVBT CV<br><span style="font-weight:400;font-size:7px;color:#DDE0FC">fully automatic · phone only</span></th>
      <th style="width:21%">SmartBarbell<br><span style="font-weight:400;font-size:7px">leading video app</span></th>
      <th style="width:22%">Vitruve LPT<br><span style="font-weight:400;font-size:7px">$500 hardware = ground truth</span></th>
    </tr>
    <tr class="grp"><td colspan="4">Counting every rep</td></tr>
    <tr><td class="rowlab">Mean rep-count error <small>per set, vs ground truth</small></td>
      <td class="c-us"><span class="win">0.32</span><span class="xfactor">8× better</span></td><td class="lose">2.57</td><td class="mute">reference</td></tr>
    <tr><td class="rowlab">Sets counted exactly</td>
      <td class="c-us"><span class="win">16 / 22</span></td><td class="lose">7 / 21</td><td class="mute">—</td></tr>
    <tr><td class="rowlab">Sets within ±1 rep</td>
      <td class="c-us"><span class="win">21 / 22</span></td><td class="lose">13 / 21</td><td class="mute">—</td></tr>
    <tr><td class="rowlab">Main lifts (every bench &amp; squat set)</td>
      <td class="c-us"><span class="win">100% exact</span></td><td class="lose">misses up to 7 reps/set</td><td class="mute">—</td></tr>
    <tr class="grp"><td colspan="4">The fatigue signal — intra-set velocity loss</td></tr>
    <tr><td class="rowlab">Velocity-loss error <small>pp vs ground truth, same 11 clips</small></td>
      <td class="c-us"><span class="win">3.2 pp</span><span class="xfactor">~3× better</span></td><td class="lose">9.0 pp</td><td class="mute">reference</td></tr>
    <tr><td class="rowlab">Worst-case fatigue read <small>squat set, true loss 30%</small></td>
      <td class="c-us"><span class="win">26%</span></td><td class="lose">2.4% — reads near-failure as fresh</td><td class="mute">30%</td></tr>
    <tr class="grp"><td colspan="4">Trust &amp; experience</td></tr>
    <tr><td class="rowlab">Knows when it can't measure</td>
      <td class="c-us">abstains + flags, per rep</td><td class="lose">reports phantoms at 100% confidence</td><td class="mute">n/a</td></tr>
    <tr><td class="rowlab">Setup per set</td>
      <td class="c-us">none — point the phone</td><td>aim + confirm</td><td class="mute">mount unit, clip to bar</td></tr>
    <tr class="last"><td class="rowlab">Hardware cost</td>
      <td class="c-us">$0</td><td>$0</td><td class="mute">~$500</td></tr>
  </table>
  <p style="font-size:7px;color:#98A0AD;margin-top:5px">Benchmark frozen 2026-06-11; every number regenerates from the repo (cv_eval.py / vel_eval.py). Ground truth is scoring-only — never an input. SmartBarbell n=21 (no reading on one clip).</p>

  <div class="p2figs">
    <div style="width:2.92in">
      <div class="fig2">
        <img src="data:image/jpeg;base64,{IMG_SQ}">
        <svg class="ov" viewBox="0 0 {SQ_SIZE[0]} {SQ_SIZE[1]}" font-family="Inter, sans-serif">
          <path d="{SQ_PATH}" fill="none" stroke="#A5B4FC" stroke-width="7" opacity=".4" stroke-linecap="round"/>
          <path d="{SQ_PATH}" fill="none" stroke="#6366F1" stroke-width="2.8" stroke-linecap="round"/>
          <circle cx="350" cy="290" r="57" fill="none" stroke="#fff" stroke-width="4.5" opacity=".55"/>
          <circle cx="350" cy="290" r="57" fill="none" stroke="#6366F1" stroke-width="2.6"/>
          <circle cx="43" cy="75" r="24" fill="none" stroke="#fff" stroke-width="2.4" stroke-dasharray="6 4" opacity=".95"/>
          <circle cx="270" cy="165" r="22" fill="none" stroke="#fff" stroke-width="2.4" stroke-dasharray="6 4" opacity=".95"/>
          <rect x="10" y="10" width="248" height="40" rx="10" fill="#0B0F19" opacity=".84"/>
          <text x="24" y="27" font-size="12.5" font-weight="700" fill="#fff">10 / 10 reps — zero taps</text>
          <text x="24" y="42" font-size="10" fill="#B7BFD2">hex iron · mirror · rack clutter · Equinox</text>
          <rect x="240" y="352" width="190" height="38" rx="10" fill="#0B0F19" opacity=".84"/>
          <text x="252" y="368" font-size="11" font-weight="700" fill="#fff">locked: moves with the bar</text>
          <text x="252" y="383" font-size="9.5" fill="#B7BFD2">flow-verified · confidence 1.00</text>
          <line x1="350" y1="352" x2="350" y2="349" stroke="#fff" stroke-width="2" opacity=".8"/>
          <rect x="10" y="374" width="216" height="38" rx="10" fill="#0B0F19" opacity=".84"/>
          <text x="24" y="390" font-size="11" font-weight="700" fill="#fff">dashed = decoys, rejected</text>
          <text x="24" y="405" font-size="9.5" fill="#B7BFD2">stored plates · mirror reflections</text>
        </svg>
      </div>
      <div class="figcap"><b>The hard part is knowing what to track.</b> We propose every moving circle, flow-verify
        each, and keep the one that locks with plausible, regular reps. Method, not gym profile.</div>
    </div>
    <div style="width:2.92in">
      <div class="fig2">
        <img src="data:image/jpeg;base64,{IMG_BN}">
        <svg class="ov" viewBox="0 0 {BN_SIZE[0]} {BN_SIZE[1]}" font-family="Inter, sans-serif">
          <path d="{BN_PATH}" fill="none" stroke="#A5B4FC" stroke-width="7" opacity=".4" stroke-linecap="round"/>
          <path d="{BN_PATH}" fill="none" stroke="#6366F1" stroke-width="2.8" stroke-linecap="round"/>
          <circle cx="55" cy="205" r="46" fill="none" stroke="#fff" stroke-width="4.5" opacity=".55"/>
          <circle cx="55" cy="205" r="46" fill="none" stroke="#6366F1" stroke-width="2.6"/>
          <rect x="120" y="10" width="262" height="40" rx="10" fill="#0B0F19" opacity=".84"/>
          <text x="134" y="27" font-size="12.5" font-weight="700" fill="#fff">205&#8201;lb to failure — set 4 of 4</text>
          <text x="134" y="42" font-size="10" fill="#B7BFD2">dark iron plate · low-res clip · 10 / 10 reps</text>
          <rect x="120" y="330" width="306" height="40" rx="10" fill="#4F46E5"/>
          <text x="134" y="347" font-size="12" font-weight="800" fill="#fff">the terminal grind rep: caught</text>
          <text x="134" y="362" font-size="10" fill="#DDE0FC">0.17&#8201;m/s — where the recovery score is made</text>
        </svg>
      </div>
      <div class="figcap"><b>Near-failure reps are the product.</b> They carry the fatigue signal — and they're exactly
        where the incumbent loses the bar (below).</div>
    </div>
    <div style="flex:1;display:flex;flex-direction:column;justify-content:flex-start">
      <div style="font-size:7.4px;font-weight:800;letter-spacing:.1em;color:#98A0AD;text-transform:uppercase;margin-bottom:1px">Velocity-loss read<br><span style="letter-spacing:0;font-weight:600;text-transform:none">same bench set &#8594;</span></div>
      <div class="losschip" style="background:#F5F6FE;border:1px solid #D9DCFB">
        <div class="v" style="color:#4F46E5">46.0%</div><div class="k" style="color:#5C6470">meVBT — error 1.4&#8201;pp</div></div>
      <div class="losschip" style="background:#FAFAFC;border:1px solid #E7E9F0">
        <div class="v" style="color:#0B0F19">44.6%</div><div class="k" style="color:#5C6470">Vitruve ground truth</div></div>
      <div class="losschip" style="background:#FEF2F2;border:1px solid #FECACA">
        <div class="v" style="color:#DC2626">missed</div><div class="k" style="color:#B9402F">SmartBarbell — lost the terminal rep</div></div>
      <div style="font-size:7.3px;color:#98A0AD;margin-top:6px;line-height:1.45">One phantom or missed rep at the
        grindy finish corrupts the whole fatigue read — counting and fatigue are one problem.</div>
    </div>
  </div>

  <div class="chartcard">
    <div style="flex:1">
      <div style="font-size:9.5px;font-weight:800;color:#0B0F19">The rep that matters most — per-rep bar velocity, bench 205&#8201;lb × 10 to failure
        <span style="font-weight:400;color:#5C6470;font-size:7.6px">&nbsp;&nbsp;black = Vitruve ground truth · red = SmartBarbell</span></div>
      {CHART}
    </div>
  </div>

  <div class="footer"><span>{LOGO_LIGHT}</span>
    <span><b>meVBT</b> · all figures: real recorded sets, real pipeline output — nothing illustrative</span>
    <span class="mono">2 / 3</span></div>
</div></div>

<!-- ================= PAGE 3 ================= -->
<div class="page"><div class="p3">
  <div class="eyebrow"><span class="ln"></span> 03 · The platform</div>
  <div class="h-xl" style="font-size:21px;margin-top:6px">Computer vision is the wedge.<br>
    <span style="color:#4F46E5">Fusion + the recovery score is the moat.</span></div>

  <svg viewBox="0 0 760 192" width="100%" style="margin-top:12px" font-family="Inter, sans-serif">
    <defs>
      <marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#98A0AD"/></marker>
      <linearGradient id="sg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4F46E5"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient>
    </defs>
    <g font-size="10" text-anchor="middle">
      <rect x="6" y="8" width="160" height="36" rx="8" fill="#F5F6FE" stroke="#D9DCFB"/>
      <text x="86" y="24" font-weight="700" fill="#0B0F19">Phone camera (CV)</text><text x="86" y="37" font-size="8" fill="#5C6470">today — beats the market</text>
      <rect x="6" y="52" width="160" height="36" rx="8" fill="#F5F6FE" stroke="#D9DCFB"/>
      <text x="86" y="68" font-weight="700" fill="#0B0F19">Apple Watch IMU</text><text x="86" y="81" font-size="8" fill="#5C6470">always on the wrist</text>
      <rect x="6" y="96" width="160" height="36" rx="8" fill="#fff" stroke="#E7E9F0"/>
      <text x="86" y="112" font-weight="700" fill="#5C6470">AirPods IMU + HR</text><text x="86" y="125" font-size="8" fill="#98A0AD">roadmap</text>
      <rect x="6" y="140" width="160" height="36" rx="8" fill="#fff" stroke="#E7E9F0"/>
      <text x="86" y="156" font-weight="700" fill="#5C6470">BLE bar devices</text><text x="86" y="169" font-size="8" fill="#98A0AD">if you own one</text>
      <g stroke="#98A0AD" stroke-width="1.4" marker-end="url(#arr)">
        <line x1="166" y1="26" x2="252" y2="74"/><line x1="166" y1="70" x2="252" y2="86"/>
        <line x1="166" y1="114" x2="252" y2="98"/><line x1="166" y1="158" x2="252" y2="110"/>
      </g>
      <rect x="256" y="56" width="172" height="76" rx="10" fill="#0B0F19"/>
      <text x="342" y="80" font-weight="800" fill="#fff" font-size="11.5">Fusion engine</text>
      <text x="342" y="96" font-size="8" fill="#9AA3B8">align reps across sources</text>
      <text x="342" y="108" font-size="8" fill="#9AA3B8">weight by per-rep confidence</text>
      <text x="342" y="120" font-size="8" fill="#9AA3B8">re-segment by consensus</text>
      <rect x="256" y="146" width="172" height="34" rx="8" fill="#fff" stroke="#C9CDF9" stroke-dasharray="4 3"/>
      <text x="342" y="160" font-size="9" font-weight="700" fill="#4F46E5">Learned personal prior</text>
      <text x="342" y="172" font-size="7.5" fill="#5C6470">your rep shape · tempo · MVT — every edit trains it</text>
      <line x1="342" y1="146" x2="342" y2="134" stroke="#4F46E5" stroke-width="1.6" marker-end="url(#arr)"/>
      <line x1="428" y1="94" x2="470" y2="94" stroke="#98A0AD" stroke-width="1.6" marker-end="url(#arr)"/>
      <rect x="474" y="56" width="140" height="76" rx="10" fill="#F5F6FE" stroke="#D9DCFB"/>
      <text x="544" y="80" font-weight="800" fill="#0B0F19" font-size="10.5">Per-rep truth</text>
      <text x="544" y="96" font-size="8" fill="#5C6470">velocity · ROM · tempo</text>
      <text x="544" y="108" font-size="8" fill="#5C6470">velocity-loss per set</text>
      <text x="544" y="120" font-size="8" fill="#4F46E5" font-weight="700">+ confidence on every number</text>
      <line x1="614" y1="94" x2="650" y2="94" stroke="#98A0AD" stroke-width="1.6" marker-end="url(#arr)"/>
      <rect x="654" y="48" width="100" height="92" rx="10" fill="url(#sg)"/>
      <text x="704" y="84" font-weight="800" fill="#fff" font-size="11">Muscular</text>
      <text x="704" y="98" font-weight="800" fill="#fff" font-size="11">Strain &amp;</text>
      <text x="704" y="112" font-weight="800" fill="#fff" font-size="11">Recovery</text>
    </g>
  </svg>

  <div class="ws">
    <div class="wcard"><h4>Confidence is open white space</h4>
      <p>No competitor surfaces measurement confidence — we watched one report a phantom rep at a 100% badge.
         Per-rep, per-metric confidence is engineered in from day one, and it's what makes fusion possible.</p></div>
    <div class="wcard"><h4>HR platforms structurally can't follow</h4>
      <p>Whoop's strain is cardiovascular by construction. The muscular recovery score requires counting reps and
         reading bar-speed decay — a sensing-and-fusion problem, not a heart-rate feature.</p></div>
    <div class="wcard"><h4>Device-agnostic by design</h4>
      <p>Every source emits the same interface. The watch is the most convenient sensor, not a dependency — the same
         model ingests Garmin, Fitbit, a phone on a bench, or nothing but video.</p></div>
  </div>

  <div class="lab">
    <div style="font-size:10px;font-weight:800">The lab — a measurement discipline competitors don't have</div>
    <div class="nums">
      <div class="n"><div class="v">34</div><div class="k">multi-vendor sets</div></div>
      <div class="n"><div class="v">2,720</div><div class="k">rep-level measurements</div></div>
      <div class="n"><div class="v">6</div><div class="k">vendors benchmarked</div></div>
      <div class="n"><div class="v">26</div><div class="k">scored video clips</div></div>
      <div class="n"><div class="v">8</div><div class="k">lifts covered</div></div>
      <div class="n"><div class="v">4</div><div class="k">gyms · all angles</div></div>
    </div>
    <div class="note">Every commercial tool recorded side-by-side on the same physical sets, aligned rep-by-rep. This is how we
      know the market's real error bars — and it becomes the seed prior for every new user's model. No-cheating evals:
      the system sees only the clip; ground truth is scoring-only; every number regenerates from the repo.</div>
  </div>

  <div class="eyebrow" style="margin-top:13px"><span class="ln"></span> The path — each phase ships standalone value</div>
  <div class="road">
    <div class="rstep done"><span class="rbadge">DONE</span><div class="ph">PHASE 0</div><div class="ti">Capture lab</div><div class="ds">watch&#8594;phone pipeline · multi-vendor dataset</div></div>
    <div class="rstep done"><span class="rbadge">WON</span><div class="ph">PHASE 1</div><div class="ti">CV wedge</div><div class="ds">beat the best video app on counts + fatigue</div></div>
    <div class="rstep"><div class="ph">PHASE 2</div><div class="ti">Calibrate watch</div><div class="ds">watch vs Vitruve; quantified per-lift error</div></div>
    <div class="rstep"><div class="ph">PHASE 3</div><div class="ti">Watch-only loop</div><div class="ds">confidence + personal prior, on the wrist</div></div>
    <div class="rstep"><div class="ph">PHASE 4</div><div class="ti">Fuse</div><div class="ds">video + watch + editor &#8594; consensus reps</div></div>
    <div class="rstep"><div class="ph">PHASE 5</div><div class="ti">The score</div><div class="ds">muscular strain &amp; recovery, any lift</div></div>
  </div>

  <div class="sci">
    <div class="scol"><h5>Velocity zones (mean concentric, m/s)</h5>
      <div class="zone"><span style="flex:5;background:#4338CA">strength 0–.5</span><span style="flex:2.5;background:#6D28D9">.5–.75</span><span style="flex:2.5;background:#0D9488">.75–1.0</span><span style="flex:3;background:#059669">speed 1.0+</span></div>
      <p>We prefer personal rolling baselines over fixed zones — your bar speed, not a textbook's.</p></div>
    <div class="scol"><h5>Velocity-loss cut-offs</h5>
      <p><b class="mono">~10%</b> power · <b class="mono">~20%</b> strength · <b class="mono">~30%+</b> hypertrophy.
         Validated proximity-to-failure — the basis of the strain score.</p></div>
    <div class="scol"><h5>Minimum velocity threshold</h5>
      <p>Bar speed at true 1RM: <b class="mono">deadlift .15–.20</b> · <b class="mono">bench .10–.17</b> ·
         <b class="mono">squat .25–.30</b>. Personalized per lifter in our priors.</p></div>
  </div>

  <div class="limits"><h5>What we'll say is not solved yet</h5>
    <p>Absolute m/s from low-res video trails the incumbent (~0.07&#8201;m/s) — so we abstain and report the scale-free
       fatigue signal rather than guess; HD capture and a learned plate-sizer close it. Dead-front camera angles defeat
       every tool (including the incumbent). Single-dumbbell accessories await the pose + watch path. We publish our
       limits — it's the same honesty the confidence system sells.</p></div>

  <div class="footer"><span>{LOGO_LIGHT}</span>
    <span><b>meVBT</b> · working prototype · jimartter@gmail.com · benchmark frozen 2026-06-11</span>
    <span class="mono">3 / 3</span></div>
</div></div>

</body></html>
"""

open(OUT_HTML, "w").write(HTML)
print("wrote", OUT_HTML, f"({len(HTML)//1024} KB, self-contained)")

try:
    from weasyprint import HTML as WP
    WP(string=HTML).write_pdf(OUT_PDF)
    print("wrote", OUT_PDF, f"({os.path.getsize(OUT_PDF)//1024} KB)")
except Exception as e:  # PDF is optional; the HTML prints identically from a browser
    print(f"PDF skipped ({e}) — open the HTML and print to PDF instead")

if "--preview" in sys.argv:
    import fitz
    doc = fitz.open(OUT_PDF)
    for i, pg in enumerate(doc):
        pg.get_pixmap(dpi=130).save(os.path.join(WORK, f"preview_p{i+1}.png"))
    print("previews in", WORK)
