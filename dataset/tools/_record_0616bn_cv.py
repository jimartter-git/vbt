"""Record the 2026-06-16 bench CV results into clips.csv, update manifest + sets.csv notes.

Findings (this session):
- ROTATION is a NON-issue: these iPhone clips carry frame.rotation=-90 (display matrix),
  which PyAVDecoder already honours -> upright 1080x1920, bar travels vertically. (My first
  probe misread the DISPLAYMATRIX side-data as 0 and a raw-decode optical-flow test saw the
  bar moving along X; both were artifacts of NOT applying the rotation. No code change needed;
  the started force_rotation override was reverted.)
- COUNTS: the AUTO (zero-tap) path is EXACT on BN-1/2/3 (10/10/10, conf 1.0, dark Rogue iron)
  and reads 11 on BN-4/5 (+1). The +1 is a real extra position cycle BOTH auto and one-tap see
  (a put-down/rack at the set end); auto's plausibility gate caught BN-2's but not 4/5's. Auto
  mean|err| 0.4 < one-tap 0.6 (one-tap's auto-located late seeds kept the put-down on 2/4/5).
- VELOCITY is UNRELIABLE on these clips: velocity-LOSS pins ~61-72% regardless of the true
  Vitruve loss (42/24/30/40/59%), and absolute m/s is hub-vs-rim scale-inflated (~3x; the seed
  sat on the small blue hub not the rim). VL is scale-invariant, so the bad VL is a PROFILE-shape
  problem (dark-iron flow velocity noise on a diagonal end-ish view), not just scale. So: COUNT is
  the trustworthy output here; velocity needs a clean side-on capture (capture ask).
"""
import csv, os
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CLIPS = os.path.join(REPO, "dataset", "clips.csv")
SETS = os.path.join(REPO, "dataset", "sets.csv")
MAN = os.path.join(REPO, "dataset", "raw", "manifest.csv")

# set -> (auto_reps, onetap_reps, VL_ours, VL_vit)
RES = {
    1: (10, 10, 61, 42), 2: (10, 11, 61, 24), 3: (10, 10, 62, 30),
    4: (11, 11, 72, 40), 5: (11, 11, 63, 59),
}
LOAD = {1: 102.1, 2: 93.0, 3: 93.0, 4: 93.0, 5: 93.0}

# ---- clips.csv rows ----
clip_cols = next(csv.reader(open(CLIPS)))
clip_rows = []
for n in range(1, 6):
    auto, onetap, vlo, vlv = RES[n]
    exact = auto == 10
    flags = "rot_handled|auto"
    flags += "|count_exact" if exact else "|over1_putdown"
    flags += "|vel_unreliable|scale_hub_suspect"     # velocity not trustworthy here
    note = (f"Bench {('225' if n==1 else '205')}lb x10, dark Rogue iron + blue hub, diagonal "
            f"end-ish view. AUTO zero-tap reps_cv {auto} "
            f"({'EXACT' if exact else '+1: a put-down/rack cycle both auto & 1-tap see'}); "
            f"1-tap(hub) {onetap}. conf 1.0, track rides the plate. "
            f"VELOCITY UNRELIABLE: velocity-loss {vlo}% vs Vitruve {vlv}% (pins ~61% across sets "
            f"= flow velocity PROFILE noise on dark iron, NOT real fatigue); abs m/s hub-vs-rim "
            f"scale-inflated. COUNT is the result; velocity needs a clean side-on capture.")
    clip_rows.append({
        "clip": f"20260616-BN_{n}.mov", "lift": "bench", "load_kg": LOAD[n], "load_unit": "lb",
        "gym": "", "equipment": "iron_round", "angle_kind": "diagonal", "angle_quality": 3,
        "background_clutter": 2, "occlusion": 1, "lighting": 3, "velocity_regime": "normal",
        "tempo_notes": ("heavy top set to near-failure (VL 42%)" if n == 1 else "back-off set"),
        "reps_cv": auto, "reps_true": 10, "mean_vel_cv": "", "cv_conf": 1.0, "cv_flags": flags,
        "has_gt": "true", "set_id": f"20260616-BN-{n}", "notes": note})

with open(CLIPS, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=clip_cols)
    for r in clip_rows:
        w.writerow(r)
print(f"clips.csv: +{len(clip_rows)} rows")

# ---- manifest notes: Pending CV -> scored ----
man_rows = list(csv.DictReader(open(MAN)))
man_cols = list(man_rows[0].keys())
for r in man_rows:
    if r["set_id"].startswith("20260616-BN-") and "Pending CV" in r["note"]:
        n = int(r["set_id"].split("-")[-1])
        auto = RES[n][0]
        r["note"] = r["note"].replace(
            "Pending CV.",
            f"AUTO zero-tap CV reps_cv {auto} ({'EXACT' if auto==10 else '+1 put-down'}) vs GT 10; "
            f"velocity unreliable (dark-iron flow profile noise, end-ish view) - count only.")
with open(MAN, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=man_cols)
    w.writeheader()
    w.writerows(man_rows)
print("manifest.csv: notes updated")

# ---- sets.csv notes: append CV + watch summary ----
set_rows = list(csv.DictReader(open(SETS)))
set_cols = list(set_rows[0].keys())
WATCH = {  # set -> short watch summary (from analysis/scripts/_watch_0616bn.py)
    1: "10 clean reps, bias -0.05 RMSE 0.077", 2: "10, +0.05 RMSE 0.101",
    3: "11 (one extra), +0.00 RMSE 0.086", 4: "9 (one short), -0.04 RMSE 0.098",
    5: "10, +0.01 RMSE 0.092"}
for r in set_rows:
    if r["set_id"].startswith("20260616-BN-"):
        n = int(r["set_id"].split("-")[-1])
        auto = RES[n][0]
        if "CV (R2 video)" not in r["notes"]:
            r["notes"] += (
                f" CV (R2 video) AUTO zero-tap: reps_cv {auto} vs GT 10 "
                f"({'EXACT' if auto==10 else '+1 put-down cycle, both paths'}), conf 1.0; "
                f"velocity UNRELIABLE on this dark-iron diagonal view (VL {RES[n][2]}% vs "
                f"Vit {RES[n][3]}% - flow profile noise; abs m/s hub-scale-inflated). "
                f"Watch IMU (bench-gated): {WATCH[n]} m/s vs Vitruve. Aggregate watch sets 1-5: "
                f"RMSE 0.091 r 0.59 - bench (slow/paused/supine) below the row quality & the "
                f"SEE<0.07 target; ROM tracks well (~0.31 vs 0.33 m).")
with open(SETS, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=set_cols)
    w.writeheader()
    w.writerows(set_rows)
print("sets.csv: notes updated")
print("DONE")
