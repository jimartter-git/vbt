#!/usr/bin/env python3
"""Generate a single self-contained flow.html for the VBT project.

Code snippets are sliced from the REAL repo files so the diagram never drifts
into placeholder code. Layout coordinates are hand-placed (all /4).
"""
import json, os

REPO = "/home/user/vbt"

def slc(path, a, b):
    with open(os.path.join(REPO, path)) as f:
        lines = f.readlines()
    return "".join(lines[a-1:b]).rstrip("\n")

def join(*chunks):
    return "\n    ...\n".join(chunks)

# ---- inline code blocks (where no single file slice tells the story) ----
RAW_INLINE = """dataset/raw/
  20260616-BN-1_watch.csv   # Apple Watch IMU @200Hz (wrist)
  20260616-BN_vitruve.csv   # Vitruve LPT export (ground truth)
  20260617-SQ-1.mov         # small upright video proxy
# suffix conventions:
#   _watch (wrist IMU) · _watch_bar (bar mount)
#   _vitruve (LPT ground truth) · -MM (different athlete)"""

VENDOR_INLINE = """# Ground truth = Vitruve; compare.py auto-prefers it
REF_PREFERENCE = ["vitruve", "stance", "metric",
                  "smartbarbell", "wl_analysis"]
# screenshot apps (Stance/SmartBarbell/Metric) -> transcribed by hand
# exports (Vitruve CSV, WL .txt) -> dataset/raw/ then wl_import.py"""

INGEST_MEAS_INLINE = """# 1. identify the vendor (dataset/INGESTION.md recipes)
# 2. collect: set_id | lift | load | RPE | which other tools
# 3. append rows  (ALIGN ON true_rep, never rep_index):
#      sets.csv         <- one row per set   (load, RPE)
#      rep_metrics.csv  <- one row / (set, vendor, rep, metric)
# 4. rebuild + sanity-check:
python dataset/tools/build_db.py
python dataset/tools/compare.py 20260529-DL-1"""

INGEST_CLIPS_INLINE = """# probe each clip -> raw/manifest.csv (storage pointer)
#   + a wide clips.csv annotation row (CV-prefilled draft count)
clip,lift,load_kg,...,angle_kind,background_clutter,lighting,
velocity_regime,reps_cv,reps_true,cv_conf,has_gt,set_id,notes"""

SETS_INLINE = """set_id,date,lift,load_kg,load_entered,load_unit,
set_index,target_reps,actual_reps,rpe_actual,notes
20260529-DL-1,2026-05-29,deadlift,149.7,330,lb,1,8,8,8,"..."
# load canonicalized to kg · rpe_actual = the prior's label"""

REPS_INLINE = """set_id,vendor,rep_index,true_rep,metric,value,unit,flag,confidence
20260529-DL-1,stance,1,1,mean_velocity,0.42,m/s,,
20260529-DL-1,stance,2,2,mean_velocity,0.47,m/s,,
20260529-DL-1,stance,3,3,mean_velocity,0.48,m/s,,
# align on true_rep (physical rep), NOT rep_index (vendor count)
# velocity-loss derived on the fly -> metrics.velocity_loss_pct"""

CLIPS_INLINE = slc("dataset/clips.csv", 1, 1)

BOARDS_INLINE = """# score our estimators against Vitruve ground truth
python analysis/scripts/cv_eval.py  --guardrail  # BLIND seed-free counts
python analysis/scripts/cv_eval.py  --auto       # no-tap flow+detect fusion
python analysis/scripts/cv_eval.py  --gate --tap # human tap path
python analysis/scripts/wave_eval.py --blind     # watch, leave-one-out"""

FUTURE_INLINE = """docs/sources-and-fusion.md  — the north star
* confidence-weighted FUSION: watch + video + BLE + AirPods
* learned rep-shape prior + manual editor for terminal reps
* learned plate detector (seed-free dark-iron CV)
* on-device real-time velocity feedback
=> a muscular STRAIN & RECOVERY score HR platforms can't see"""

# ---------------------------------------------------------------------------
NODES = [
  # id, label, sub, layer, x, y, w, h, file, lang, code, desc, accent
  dict(id="watch", label="Apple Watch capture", sub="Watch/Services/", layer="device",
       x=96, y=48, w=336, h=92, file="Watch/Services/MotionRecorder.swift",
       lang="swift", code=slc("Watch/Services/MotionRecorder.swift", 75, 97),
       desc="The watchOS app holds an <b>HKWorkoutSession</b> open so the sensors stay "
            "alive, while <b>CMBatchedSensorManager</b> streams device motion at ~200 Hz "
            "(user-accel, gravity, attitude quaternion, gyro, mag). Device-validated on a "
            "real Ultra. Each set is written to CSV with a UTC↔uptime clock anchor, then "
            "<code>transferFile</code>'d to the phone."),
  dict(id="video", label="Phone video capture", sub="iOS/Services/", layer="device",
       x=552, y=48, w=336, h=92, file="iOS/Services/VideoRecorder.swift",
       lang="swift", code=slc("iOS/Services/VideoRecorder.swift", 27, 51),
       desc="The iPhone records each set as 1080p60 HEVC <b>.mov</b> (no audio, to keep the "
            "AirPods motion route clean) plus a JSON sidecar carrying the <i>same</i> clock "
            "anchor as the watch — so video and watch are time-alignable. HD masters are too "
            "big for git, so they go to R2."),
  dict(id="vendor", label="Vendor / BLE devices", sub="ground truth", layer="device",
       x=1008, y=48, w=336, h=92, file="dataset/tools/compare.py",
       lang="python", code=VENDOR_INLINE,
       desc="Commercial tools measure the same set. <b>Vitruve</b> (a linear position "
            "transducer) is the established <b>ground-truth reference</b>; SmartBarbell, "
            "Stance and Metric are comparison sources. Screenshot-only apps are transcribed "
            "by hand; exports arrive as CSV."),

  dict(id="raw", label="dataset/raw/", sub="committed signals", layer="data",
       x=320, y=224, w=320, h=92, file="dataset/raw/",
       lang="text", code=RAW_INLINE,
       desc="Git-versioned raw time-series that fit in git: watch IMU "
            "(<code>*_watch.csv</code>), Vitruve exports (<code>*_vitruve.csv</code>), and "
            "small upright video proxies. The byte-level source of truth for everything that "
            "isn't HD video."),
  dict(id="r2", label="Cloudflare R2 + manifest", sub="vbt-video bucket", layer="data",
       x=800, y=224, w=320, h=92, file="analysis/vbt_video/clip_store.py",
       lang="python", code=slc("analysis/vbt_video/clip_store.py", 102, 133),
       desc="HD/4K video masters live in the R2 bucket <b>vbt-video</b> — <i>don't commit HD "
            "video to git</i>. The repo keeps only a pointer row in "
            "<code>dataset/raw/manifest.csv</code> (sha/bytes/res/key); "
            "<code>resolve_clip()</code> fetches local → cache → R2 on demand."),

  dict(id="ingest_meas", label="Ingest measurements", sub="INGESTION.md", layer="run",
       x=96, y=400, w=336, h=92, file="dataset/INGESTION.md · dataset/tools/wl_import.py",
       lang="bash", code=INGEST_MEAS_INLINE,
       desc="The entry workflow you <b>run</b> per upload: identify the vendor, collect the "
            "linking metadata (<code>set_id · lift · load · RPE · which tools</code>), then "
            "append a <code>sets.csv</code> row and the per-rep <code>rep_metrics.csv</code> "
            "rows — always aligned on <b>true_rep</b>, never the vendor's own count."),
  dict(id="ingest_clips", label="Ingest video corpus", sub="clips.csv + manifest", layer="run",
       x=520, y=400, w=336, h=92, file="dataset/clips.csv · dataset/ANNOTATIONS.md",
       lang="text", code=INGEST_CLIPS_INLINE,
       desc="A clip is probed into <code>manifest.csv</code> (the R2 pointer) and a wide "
            "<code>clips.csv</code> row of human annotations (camera angle, clutter, rep "
            "regime, plate type) plus a CV-prefilled draft count — the labeled bench for "
            "generalizing the CV estimator."),

  dict(id="sets", label="sets.csv", sub="one row / set", layer="db",
       x=64, y=576, w=176, h=104, file="dataset/sets.csv",
       lang="text", code=SETS_INLINE,
       desc="The set-level ledger: date, lift, load (kg + as-entered), rep count, and your "
            "subjective <b>RPE</b> — the label the RPE/fatigue model is eventually trained "
            "against."),
  dict(id="reps", label="rep_metrics.csv", sub="THE source of truth", layer="db",
       x=256, y=576, w=240, h=104, file="dataset/rep_metrics.csv", accent=True,
       lang="text", code=REPS_INLINE,
       desc="<b>The heart of the database.</b> A tidy long table: one row per "
            "<code>(set, vendor, rep, metric)</code>. Two rep keys — <code>rep_index</code> "
            "(the vendor's own count) and <code>true_rep</code> (the physical rep, the "
            "cross-vendor alignment key). Every velocity, ROM and the <b>velocity-loss "
            "fatigue signal</b> is derived from here on the fly — never frozen."),
  dict(id="clips", label="clips.csv", sub="CV corpus", layer="db",
       x=512, y=576, w=176, h=104, file="dataset/clips.csv",
       lang="text", code=CLIPS_INLINE,
       desc="One wide row per CV-training clip: the human annotations plus a draft count. "
            "Pairs with <code>manifest.csv</code> (where the bytes live in R2). The "
            "generalization bench for computer vision."),
  dict(id="priors", label="priors/", sub="cold-start priors", layer="db",
       x=712, y=576, w=176, h=104, file="dataset/priors/",
       lang="text", code=slc("dataset/priors/deadlift_rom.csv", 1, 3),
       desc="Per-lift ROM priors and RPE→velocity curves derived from the Vitruve rows "
            "(<code>derive_rom_priors.py</code>). <b>Advisory only</b> (they flag, never "
            "gate); they seed the app's per-user prior and personal MVTs (deadlift ≈ "
            "0.15–0.20 m/s)."),

  dict(id="build_db", label="build_db.py → SQLite", sub="rebuilt artifact", layer="run",
       x=256, y=792, w=240, h=92, file="dataset/tools/build_db.py",
       lang="python", code=slc("dataset/tools/build_db.py", 30, 54),
       desc="Rebuilds <code>dataset.sqlite</code> from the source-of-truth CSVs (stdlib "
            "only). The SQLite file is a <b>regenerable, gitignored artifact</b> — the CSVs "
            "are canonical. Run after every ingest; <code>compare.py</code> reads it for "
            "cross-vendor agreement."),

  dict(id="watch_pipe", label="Watch IMU pipeline", sub="vbt_analysis", layer="run",
       x=952, y=576, w=216, h=104, file="analysis/vbt_analysis/wave_segment.py",
       lang="python", code=slc("analysis/vbt_analysis/wave_segment.py", 214, 241),
       desc="<code>load_session</code> → <code>vertical_acceleration</code> (rotate to world "
            "frame via the quaternion, isolate vertical) → <code>wave_segment.segment</code> "
            "— <b>one lift-agnostic config</b>: reps are the set's modal up-excursions; "
            "unrack/putdown stripped structurally → ZUPT-anchored velocity. 16/18 sessions "
            "exact, RMSE ~0.07 m/s vs Vitruve."),
  dict(id="cv_pipe", label="Video CV pipeline", sub="vbt_video", layer="run",
       x=1192, y=576, w=216, h=104, file="analysis/vbt_video/pipeline.py",
       lang="python", code=slc("analysis/vbt_video/pipeline.py", 250, 272),
       desc="<code>resolve_clip</code> → PyAV frames → <code>track</code> (FlowTracker; seed "
            "candidates + motion-blob recall localize the <i>working</i> plate, not a decoy) "
            "→ <code>trajectory_to_reps</code> → <b>honesty gate</b> (a right count needs the "
            "right track) → <code>VideoVelocitySource.estimate</code>. Emits vendor "
            "<code>mevbt_cv</code>; beats SmartBarbell on counts and velocity-loss."),

  dict(id="boards", label="Eval boards", sub="cv_eval · wave_eval", layer="run",
       x=952, y=792, w=216, h=92, file="analysis/scripts/cv_eval.py · wave_eval.py",
       lang="bash", code=BOARDS_INLINE,
       desc="Scoreboards that score our estimators against Vitruve. "
            "<code>--guardrail</code> headlines the <b>BLIND seed-free</b> count (separating "
            "product-legit taps from oracle seeds); <code>wave_eval --blind</code> does "
            "leave-one-session-out. Provenance-tagged so no number is reported in-sample."),
  dict(id="coverage", label="coverage.py", sub="corpus reconcile", layer="run",
       x=1192, y=792, w=216, h=92, file="analysis/scripts/coverage.py",
       lang="python", code=slc("analysis/scripts/coverage.py", 89, 116),
       desc="Guards the curated-subset blind spot: reconciles the hand-maintained eval boards "
            "against the <b>full corpus</b> (every clip in manifest ∪ local, every "
            "<code>*_watch.csv</code>, all GT rows) and exits non-zero on a gap. Run at the "
            "start of any CV/watch work and after every upload."),

  dict(id="velsource", label="VelocitySource contract", sub="Packages/VBTCore", layer="contract",
       x=512, y=968, w=336, h=104,
       file="Packages/VBTCore/Sources/VBTCore/VelocitySource.swift",
       lang="swift", code=slc("Packages/VBTCore/Sources/VBTCore/VelocitySource.swift", 111, 120),
       desc="The one cross-source abstraction. Every source — watch IMU, BLE, video, AirPods "
            "— emits the <b>same shape</b>: per-rep (boundaries, velocity, ROM) + a "
            "confidence, plus a <code>SetSummary</code> with the canonical "
            "<code>velocityLossPct</code> (kept in lock-step with the Python metric). What "
            "makes fusion and graceful degradation possible."),
  dict(id="future", label="Future: fusion · app · strain", sub="the product bet", layer="future",
       x=952, y=968, w=456, h=104, file="docs/sources-and-fusion.md",
       lang="text", code=FUTURE_INLINE,
       desc="Where it's all heading (one node, many dreams): confidence-weighted multi-source "
            "<b>fusion</b> with a learned rep-shape prior + manual editor; a learned plate "
            "detector for seed-free dark-iron CV; on-device real-time velocity; and the "
            "payoff — a <b>muscular strain &amp; recovery score</b> HR platforms can't see."),
]

EDGES = [
  ("watch","raw",None,False), ("vendor","raw",None,False), ("video","r2",None,False),
  ("raw","ingest_meas",None,False), ("r2","ingest_clips",None,False),
  ("ingest_meas","sets",None,False), ("ingest_meas","reps",None,False),
  ("ingest_clips","clips",None,False),
  ("reps","priors","derive",True),
  ("reps","build_db","rebuild",False),
  ("raw","watch_pipe","*_watch.csv",True),
  ("r2","cv_pipe","resolve_clip",True),
  ("watch_pipe","boards",None,False), ("cv_pipe","boards",None,False),
  ("reps","boards","ground truth",True),
  ("reps","coverage","reconcile",True),
  ("watch_pipe","velsource","conforms",False), ("cv_pipe","velsource","conforms",False),
  ("priors","velsource","seeds prior",True),
  ("velsource","future",None,False),
  ("boards","future","findings",True),
]

STEP = ["watch","raw","ingest_meas","reps","build_db","cv_pipe","boards","velsource","future"]

data = {
  "nodes": NODES,
  "edges": [{"s":s,"t":t,"label":l,"dashed":d} for (s,t,l,d) in EDGES],
  "step": STEP,
}
DATA_JSON = json.dumps(data, ensure_ascii=False)

HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VBT — how data is stored, where it flows, when you run things</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --serif:'Instrument Serif',Georgia,'Times New Roman',serif;
  --sans:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;
  --mono:'JetBrains Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  --accent:#e8a13a;
}
html[data-theme="dark"]{
  --bg:#000; --panel:#0d0d0d; --fg:#ededeb; --muted:#8a8a84; --faint:#5c5c57;
  --hair:#262624; --node:#0f0f0f; --edge:#3a3a37; --edge-on:#cfcfca;
  --t-device:rgba(122,156,196,.12); --b-device:rgba(150,180,214,.42);
  --t-data:rgba(206,170,112,.12);   --b-data:rgba(214,180,124,.46);
  --t-run:rgba(126,190,150,.12);    --b-run:rgba(150,202,168,.44);
  --t-contract:rgba(176,150,206,.12);--b-contract:rgba(190,166,214,.46);
  --t-future:rgba(140,140,140,.08); --b-future:rgba(150,150,150,.34);
  --code-bg:#070707;
}
html[data-theme="light"]{
  --bg:#fafaf7; --panel:#fff; --fg:#1a1a18; --muted:#6a6a63; --faint:#9a9a92;
  --hair:#e4e4dc; --node:#fff; --edge:#cfcfc7; --edge-on:#2a2a26;
  --t-device:rgba(70,110,165,.10); --b-device:rgba(70,110,165,.40);
  --t-data:rgba(168,120,40,.10);   --b-data:rgba(168,120,40,.42);
  --t-run:rgba(56,150,92,.10);     --b-run:rgba(56,150,92,.40);
  --t-contract:rgba(120,86,170,.10);--b-contract:rgba(120,86,170,.42);
  --t-future:rgba(120,120,120,.07);--b-future:rgba(120,120,120,.34);
  --code-bg:#f4f3ee;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--fg);font-family:var(--sans);
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased;overflow:hidden}
header{position:fixed;top:0;left:0;right:0;height:72px;z-index:30;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;border-bottom:1px solid var(--hair);background:var(--bg)}
.brand{display:flex;flex-direction:column;gap:2px}
.brand h1{font-family:var(--serif);font-weight:400;font-size:30px;line-height:1;margin:0;letter-spacing:.2px}
.brand .tag{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.3px}
.controls{display:flex;align-items:center;gap:8px}
.btn{font-family:var(--sans);font-size:13px;color:var(--fg);background:transparent;
  border:1px solid var(--hair);border-radius:8px;padding:8px 14px;cursor:pointer;
  display:inline-flex;align-items:center;gap:7px;transition:border-color .15s,color .15s}
.btn:hover{border-color:var(--b-data)}
.btn .k{font-family:var(--mono);font-size:10px;color:var(--faint)}
.btn.live{border-color:var(--accent);color:var(--accent)}
#stage{position:absolute;inset:72px 0 0 0;cursor:grab;touch-action:none}
#stage.grabbing{cursor:grabbing}
svg{width:100%;height:100%;display:block}
.legend{position:fixed;left:28px;bottom:24px;z-index:20;display:flex;gap:18px;
  font-family:var(--mono);font-size:11px;color:var(--muted);
  background:var(--bg);padding:8px 14px;border:1px solid var(--hair);border-radius:8px}
.legend span{display:inline-flex;align-items:center;gap:7px}
.legend i{width:10px;height:10px;border-radius:3px;display:inline-block;border:1px solid}
.lg-device{background:var(--t-device);border-color:var(--b-device)}
.lg-data{background:var(--t-data);border-color:var(--b-data)}
.lg-run{background:var(--t-run);border-color:var(--b-run)}
.lg-store{background:var(--t-contract);border-color:var(--b-contract)}
.hint{position:fixed;right:28px;bottom:24px;z-index:20;font-family:var(--mono);
  font-size:11px;color:var(--faint)}
/* nodes */
.node{cursor:pointer}
.nbox{fill:var(--node);stroke:var(--hair);stroke-width:1;rx:8}
.node .nbox{transition:stroke .15s,filter .15s}
.layer-device .nbox{fill:var(--t-device);stroke:var(--b-device)}
.layer-data .nbox{fill:var(--t-data);stroke:var(--b-data)}
.layer-run .nbox{fill:var(--t-run);stroke:var(--b-run)}
.layer-contract .nbox{fill:var(--t-contract);stroke:var(--b-contract)}
.layer-future .nbox{fill:var(--t-future);stroke:var(--b-future);stroke-dasharray:5 4}
.node.accent .nbox{fill:var(--t-data);stroke:var(--accent);stroke-width:1.5}
.node:hover .nbox{stroke:var(--edge-on)}
.node.sel .nbox{stroke:var(--edge-on);stroke-width:1.5}
.node.step .nbox{stroke:var(--accent);stroke-width:2}
.nlabel{height:100%;display:flex;flex-direction:column;justify-content:center;
  padding:0 16px;pointer-events:none;font-family:var(--sans)}
.ntitle{font-size:15px;font-weight:600;color:var(--fg);line-height:1.2}
.node.accent .ntitle{color:var(--accent)}
.nsub{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:4px;letter-spacing:.2px}
.dim .node:not(.rel){opacity:.32;transition:opacity .2s}
.dim .edge:not(.rel){opacity:.12;transition:opacity .2s}
/* edges */
.edge path{fill:none;stroke:var(--edge);stroke-width:1.4;transition:stroke .15s,opacity .2s}
.edge.dash path{stroke-dasharray:5 5}
.edge.rel path,.edge.on path{stroke:var(--edge-on);stroke-width:1.8}
.edge .elabel{font-family:var(--mono);font-size:10px;fill:var(--muted)}
.edge .elabel-bg{fill:var(--bg)}
.edge.draw path{stroke-dasharray:1000;stroke-dashoffset:1000;animation:draw .6s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}
/* side panel */
#scrim{position:fixed;inset:0;z-index:40;background:rgba(0,0,0,.35);opacity:0;
  pointer-events:none;transition:opacity .2s}
#scrim.show{opacity:1;pointer-events:auto}
#panel{position:fixed;top:0;right:0;bottom:0;width:420px;max-width:92vw;z-index:50;
  background:var(--panel);border-left:1px solid var(--hair);
  transform:translateX(100%);transition:transform .26s cubic-bezier(.4,0,.2,1);
  display:flex;flex-direction:column;overflow:hidden}
#panel.show{transform:none}
.p-head{padding:24px 24px 16px;border-bottom:1px solid var(--hair)}
.p-chip{display:inline-block;font-family:var(--mono);font-size:10px;letter-spacing:.6px;
  text-transform:uppercase;color:var(--muted);border:1px solid var(--hair);
  border-radius:6px;padding:3px 8px;margin-bottom:12px}
.p-title{font-family:var(--serif);font-weight:400;font-size:26px;line-height:1.1;margin:0 0 8px}
.p-file{font-family:var(--mono);font-size:11.5px;color:var(--muted);word-break:break-all}
.p-body{padding:20px 24px;overflow-y:auto;flex:1}
.p-desc{font-size:14px;line-height:1.62;color:var(--fg);margin:0 0 20px}
.p-desc b{font-weight:600}
.p-desc code{font-family:var(--mono);font-size:12px;background:var(--code-bg);
  padding:1px 5px;border-radius:4px;color:var(--fg)}
.p-codewrap{border:1px solid var(--hair);border-radius:8px;overflow:hidden;background:var(--code-bg)}
.p-codehdr{font-family:var(--mono);font-size:10px;color:var(--faint);
  padding:8px 14px;border-bottom:1px solid var(--hair);letter-spacing:.4px;text-transform:uppercase}
pre{margin:0;padding:14px;overflow-x:auto;font-family:var(--mono);font-size:11.5px;
  line-height:1.62;color:var(--fg);white-space:pre;tab-size:4}
.tok-com{color:var(--faint);font-style:italic}
.tok-str{color:#9bbf86}
html[data-theme="light"] .tok-str{color:#3f7a32}
.tok-kw{color:#cf9d6a}
html[data-theme="light"] .tok-kw{color:#9a5b16}
.tok-num{color:#7fa6c9}
html[data-theme="light"] .tok-num{color:#3d6e98}
.p-close{position:absolute;top:18px;right:18px;width:32px;height:32px;border:1px solid var(--hair);
  background:transparent;color:var(--fg);border-radius:8px;cursor:pointer;font-size:16px;line-height:1}
.p-close:hover{border-color:var(--edge-on)}
@media(max-width:760px){.brand h1{font-size:24px}.legend{display:none}}
</style>
</head>
<body>
<header>
  <div class="brand">
    <h1>VBT data flow</h1>
    <div class="tag">how it's stored · where it flows · when you run things</div>
  </div>
  <div class="controls">
    <button class="btn" id="step">▷ Step through</button>
    <button class="btn" id="fit">Reset view <span class="k">dblclick</span></button>
    <button class="btn" id="theme">◐ Theme</button>
  </div>
</header>

<div id="stage">
  <svg id="svg" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="var(--edge)"/>
      </marker>
      <marker id="arrow-on" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="var(--edge-on)"/>
      </marker>
    </defs>
    <g id="viewport">
      <g id="edges"></g>
      <g id="nodes"></g>
    </g>
  </svg>
</div>

<div class="legend">
  <span><i class="lg-device"></i>capture / device</span>
  <span><i class="lg-data"></i>storage / data</span>
  <span><i class="lg-run"></i>run / pipeline</span>
  <span><i class="lg-store"></i>contract</span>
</div>
<div class="hint">drag to pan · scroll to zoom · click a node</div>

<div id="scrim"></div>
<aside id="panel" aria-hidden="true">
  <button class="p-close" id="pclose" aria-label="Close">✕</button>
  <div class="p-head">
    <span class="p-chip" id="pchip"></span>
    <h2 class="p-title" id="ptitle"></h2>
    <div class="p-file" id="pfile"></div>
  </div>
  <div class="p-body">
    <p class="p-desc" id="pdesc"></p>
    <div class="p-codewrap">
      <div class="p-codehdr" id="pcodehdr"></div>
      <pre><code id="pcode"></code></pre>
    </div>
  </div>
</aside>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const NS = 'http://www.w3.org/2000/svg';
const XHTML = 'http://www.w3.org/1999/xhtml';
const byId = {}; DATA.nodes.forEach(n=>byId[n.id]=n);
const VIEW_W = 1440, VIEW_H = 1128;
const svg = document.getElementById('svg');
svg.setAttribute('viewBox', `0 0 ${VIEW_W} ${VIEW_H}`);
const gNodes = document.getElementById('nodes');
const gEdges = document.getElementById('edges');

/* ---------- edge geometry ---------- */
function anchors(s,t){
  const scx=s.x+s.w/2, scy=s.y+s.h/2, tcx=t.x+t.w/2, tcy=t.y+t.h/2;
  const dx=tcx-scx, dy=tcy-scy;
  let p0,p3,c1,c2;
  if(Math.abs(dy)>=Math.abs(dx)){           // vertical-dominant
    if(dy>0){p0=[scx,s.y+s.h]; p3=[tcx,t.y];}
    else    {p0=[scx,s.y];     p3=[tcx,t.y+t.h];}
    const my=(p0[1]+p3[1])/2; c1=[p0[0],my]; c2=[p3[0],my];
  }else{                                     // horizontal-dominant
    if(dx>0){p0=[s.x+s.w,scy]; p3=[t.x,tcy];}
    else    {p0=[s.x,scy];     p3=[t.x+t.w,tcy];}
    const mx=(p0[0]+p3[0])/2; c1=[mx,p0[1]]; c2=[mx,p3[1]];
  }
  return {p0,p3,c1,c2};
}
const edgeEls=[];
DATA.edges.forEach((e,i)=>{
  const s=byId[e.s], t=byId[e.t]; const a=anchors(s,t);
  const g=document.createElementNS(NS,'g');
  g.setAttribute('class','edge'+(e.dashed?' dash':''));
  g.dataset.s=e.s; g.dataset.t=e.t;
  const p=document.createElementNS(NS,'path');
  const d=`M${a.p0[0]},${a.p0[1]} C${a.c1[0]},${a.c1[1]} ${a.c2[0]},${a.c2[1]} ${a.p3[0]},${a.p3[1]}`;
  p.setAttribute('d',d); p.setAttribute('marker-end','url(#arrow)');
  g.appendChild(p);
  if(e.label){
    const mx=(a.p0[0]+a.p3[0])/2, my=(a.p0[1]+a.p3[1])/2;
    const bg=document.createElementNS(NS,'rect');
    const w=e.label.length*5.6+8;
    bg.setAttribute('x',mx-w/2); bg.setAttribute('y',my-8); bg.setAttribute('width',w);
    bg.setAttribute('height',14); bg.setAttribute('class','elabel-bg'); bg.setAttribute('rx',3);
    const tx=document.createElementNS(NS,'text');
    tx.setAttribute('x',mx); tx.setAttribute('y',my+2.5); tx.setAttribute('text-anchor','middle');
    tx.setAttribute('class','elabel'); tx.textContent=e.label;
    g.appendChild(bg); g.appendChild(tx);
  }
  gEdges.appendChild(g); edgeEls.push({el:g,p,e});
});

/* ---------- nodes ---------- */
DATA.nodes.forEach(n=>{
  const g=document.createElementNS(NS,'g');
  g.setAttribute('class',`node layer-${n.layer}`+(n.accent?' accent':''));
  g.dataset.id=n.id;
  const r=document.createElementNS(NS,'rect');
  r.setAttribute('x',n.x); r.setAttribute('y',n.y); r.setAttribute('width',n.w);
  r.setAttribute('height',n.h); r.setAttribute('rx',8); r.setAttribute('class','nbox');
  g.appendChild(r);
  const fo=document.createElementNS(NS,'foreignObject');
  fo.setAttribute('x',n.x); fo.setAttribute('y',n.y); fo.setAttribute('width',n.w); fo.setAttribute('height',n.h);
  const div=document.createElementNS(XHTML,'div'); div.setAttribute('class','nlabel');
  const t=document.createElementNS(XHTML,'div'); t.setAttribute('class','ntitle'); t.textContent=n.label;
  const s=document.createElementNS(XHTML,'div'); s.setAttribute('class','nsub'); s.textContent=n.sub;
  div.appendChild(t); div.appendChild(s); fo.appendChild(div); g.appendChild(fo);
  g.addEventListener('click',ev=>{ev.stopPropagation(); openPanel(n.id);});
  g.addEventListener('mouseenter',()=>highlight(n.id));
  g.addEventListener('mouseleave',()=>{ if(!stepping) clearHighlight();});
  gNodes.appendChild(g);
});

/* ---------- highlight related ---------- */
function highlight(id){
  document.body.classList.add('dim');
  const rel=new Set([id]);
  edgeEls.forEach(({el,e})=>{
    if(e.s===id||e.t===id){el.classList.add('rel'); rel.add(e.s); rel.add(e.t);}
    else el.classList.remove('rel');
  });
  [...gNodes.children].forEach(g=>g.classList.toggle('rel',rel.has(g.dataset.id)));
}
function clearHighlight(){
  document.body.classList.remove('dim');
  edgeEls.forEach(({el})=>el.classList.remove('rel'));
  [...gNodes.children].forEach(g=>g.classList.remove('rel'));
}

/* ---------- syntax highlight ---------- */
const KW=/\b(def|class|return|import|from|if|elif|else|for|while|in|not|and|or|None|True|False|with|as|lambda|let|var|func|struct|protocol|enum|public|private|guard|self|final|async|await|throws|try|in)\b/;
const TOK=new RegExp('(#.*$|//.*$)|("(?:[^"\\\\]|\\\\.)*"|\'(?:[^\'\\\\]|\\\\.)*\')|'+KW.source+'|\\b(\\d+\\.?\\d*)\\b','gm');
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function hl(code){
  let out='', last=0, m;
  TOK.lastIndex=0;
  while((m=TOK.exec(code))){
    out+=esc(code.slice(last,m.index));
    if(m[1]) out+='<span class="tok-com">'+esc(m[1])+'</span>';
    else if(m[2]) out+='<span class="tok-str">'+esc(m[2])+'</span>';
    else if(m[3]) out+='<span class="tok-kw">'+esc(m[3])+'</span>';
    else if(m[4]) out+='<span class="tok-num">'+esc(m[4])+'</span>';
    else out+=esc(m[0]);
    last=m.index+m[0].length;
  }
  out+=esc(code.slice(last));
  return out;
}

/* ---------- side panel ---------- */
const panel=document.getElementById('panel'), scrim=document.getElementById('scrim');
function openPanel(id){
  const n=byId[id];
  document.getElementById('pchip').textContent=n.layer;
  document.getElementById('ptitle').textContent=n.label;
  document.getElementById('pfile').textContent=n.file;
  document.getElementById('pdesc').innerHTML=n.desc;
  document.getElementById('pcodehdr').textContent=n.lang;
  document.getElementById('pcode').innerHTML=hl(n.code);
  panel.classList.add('show'); scrim.classList.add('show'); panel.setAttribute('aria-hidden','false');
  [...gNodes.children].forEach(g=>g.classList.toggle('sel',g.dataset.id===id));
  if(!stepping) highlight(id);
}
function closePanel(){
  panel.classList.remove('show'); scrim.classList.remove('show'); panel.setAttribute('aria-hidden','true');
  [...gNodes.children].forEach(g=>g.classList.remove('sel'));
  if(!stepping) clearHighlight();
}
scrim.addEventListener('click',closePanel);
document.getElementById('pclose').addEventListener('click',closePanel);

/* ---------- pan & zoom ---------- */
const stage=document.getElementById('stage'), vp=document.getElementById('viewport');
let tx=0,ty=0,scale=1;
function apply(){vp.setAttribute('transform',`translate(${tx},${ty}) scale(${scale})`);}
function fit(){
  const r=stage.getBoundingClientRect();
  const pad=64;
  const sx=(r.width-pad*2)/VIEW_W, sy=(r.height-pad*2)/VIEW_H;
  scale=Math.min(sx,sy,1.4);
  tx=(r.width-VIEW_W*scale)/2; ty=(r.height-VIEW_H*scale)/2;
  apply();
}
stage.addEventListener('wheel',ev=>{
  ev.preventDefault();
  const r=stage.getBoundingClientRect();
  const mx=ev.clientX-r.left, my=ev.clientY-r.top;
  const f=Math.exp(-ev.deltaY*0.0015);
  const ns=Math.min(3,Math.max(0.3,scale*f));
  tx=mx-(mx-tx)*(ns/scale); ty=my-(my-ty)*(ns/scale); scale=ns; apply();
},{passive:false});
let dragging=false,sxp=0,syp=0,moved=false;
stage.addEventListener('pointerdown',ev=>{dragging=true;moved=false;sxp=ev.clientX-tx;syp=ev.clientY-ty;stage.classList.add('grabbing');stage.setPointerCapture(ev.pointerId);});
stage.addEventListener('pointermove',ev=>{if(!dragging)return;tx=ev.clientX-sxp;ty=ev.clientY-syp;moved=true;apply();});
stage.addEventListener('pointerup',ev=>{dragging=false;stage.classList.remove('grabbing');});
stage.addEventListener('dblclick',fit);
stage.addEventListener('click',ev=>{if(ev.target===stage||ev.target===svg){closePanel();}});

/* ---------- step-through ---------- */
let stepping=false, stepTimer=null, stepIx=0;
const stepBtn=document.getElementById('step');
function stepReset(){
  stepping=false; clearTimeout(stepTimer); stepBtn.classList.remove('live');
  stepBtn.textContent='▷ Step through';
  [...gNodes.children].forEach(g=>g.classList.remove('step'));
  edgeEls.forEach(({el})=>el.classList.remove('on','draw'));
  clearHighlight();
}
function stepGo(){
  if(stepIx>=DATA.step.length){ stepBtn.textContent='↺ Replay'; stepping=false; clearTimeout(stepTimer); return; }
  const id=DATA.step[stepIx];
  document.body.classList.add('dim');
  [...gNodes.children].forEach(g=>{
    if(g.dataset.id===id){g.classList.add('step','rel');}
  });
  // light up edges that connect an already-shown node to this one
  const shown=new Set(DATA.step.slice(0,stepIx+1));
  edgeEls.forEach(({el,e})=>{
    if(e.t===id && shown.has(e.s)){el.classList.add('on','rel','draw');}
    if(e.s===id||e.t===id){el.classList.add('rel');}
  });
  byId[id]&&[...gNodes.children].forEach(g=>{ if(shown.has(g.dataset.id)) g.classList.add('rel'); });
  stepIx++;
  stepTimer=setTimeout(stepGo,820);
}
stepBtn.addEventListener('click',()=>{
  if(stepping){stepReset();return;}
  if(stepBtn.textContent.startsWith('↺')){ /* replay */ }
  stepReset(); stepping=true; stepIx=0; stepBtn.classList.add('live'); stepBtn.textContent='■ Stop';
  closePanel(); stepGo();
});

/* ---------- theme ---------- */
const root=document.documentElement;
const saved=localStorage.getItem('vbt-flow-theme'); if(saved) root.setAttribute('data-theme',saved);
document.getElementById('theme').addEventListener('click',()=>{
  const next=root.getAttribute('data-theme')==='dark'?'light':'dark';
  root.setAttribute('data-theme',next); localStorage.setItem('vbt-flow-theme',next);
});

/* ---------- keys ---------- */
document.addEventListener('keydown',ev=>{
  if(ev.key==='Escape'){ if(stepping)stepReset(); else closePanel(); }
});
document.getElementById('fit').addEventListener('click',fit);
window.addEventListener('resize',fit);
fit();
</script>
</body>
</html>
"""

out = HTML.replace("__DATA__", DATA_JSON)
with open(os.path.join(REPO, "flow.html"), "w") as f:
    f.write(out)
print("wrote", os.path.join(REPO, "flow.html"), len(out), "bytes")
