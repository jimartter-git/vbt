"""Update 06-16 bench CV records after the un/rerack fix (horizontal-aware merge +
transit gate, gated behind VideoConfig.transit_aware; rim_px scale).

Before: AUTO over-counted BN-4/5 (11) and velocity was meaningless (VL pinned ~61%,
abs m/s ~3x hub-scale-inflated). After (one-tap hub seed + human-confirmed deep-dish
rim + transit_aware): reps 10/10 EXACT all 5, abs MV RMSE ~0.04 vs Vitruve (mean 0.040
≈ SmartBarbell 0.039 — TIED, was a clear SB win), VL within ~4pp on 3/5.
"""
import csv, os
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CLIPS = os.path.join(REPO, "dataset", "clips.csv")
SETS = os.path.join(REPO, "dataset", "sets.csv")
MAN = os.path.join(REPO, "dataset", "raw", "manifest.csv")

# set -> (abs_rmse, sb_rmse, vl_ours, vl_vit)
RES = {1:(0.071,0.027,39,42), 2:(0.027,0.044,31,24), 3:(0.035,0.056,42,30),
       4:(0.042,0.033,44,40), 5:(0.023,0.033,55,59)}

# clips.csv: reps_cv now 10 (tap, EXACT); flags + notes updated
rows = list(csv.DictReader(open(CLIPS))); cols = list(rows[0].keys())
for r in rows:
    if r["set_id"].startswith("20260616-BN-"):
        n = int(r["set_id"].split("-")[-1]); ar, sr, vo, vv = RES[n]
        r["reps_cv"] = 10
        r["cv_conf"] = 1.0
        r["cv_flags"] = "rot_handled|tap+rim|transit_gated|count_exact|vel_competitive"
        r["notes"] = (f"Bench {('225' if n==1 else '205')}lb x10, dark Rogue DEEP-DISH iron + blue "
                      f"hub, head-on rack view (lifter un/reracks the bar). FIXED 2026-06-16: the "
                      f"un/rerack horizontal transit USED to over-count (BN-4/5=11) + tank last-rep "
                      f"velocity; horizontal-aware merge + transit gate (VideoConfig.transit_aware, "
                      f"tap path) -> reps_cv 10 EXACT, conf 1.0. Velocity via human-confirmed RIM "
                      f"(deep-dish 45 ~570px vs the 72px hub = 7x scale error): abs MV RMSE {ar:.3f} "
                      f"vs Vitruve (SB {sr:.3f}); VL {vo}% vs Vit {vv}%. Mean abs over the 5: ours "
                      f"0.040 ~ SB 0.039 (tied). Plates: set1 2x45, sets2-5 a 10+25 in front of one "
                      f"deep-dish 45. Westwood Athletics.")
with open(CLIPS, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print("clips.csv updated (reps_cv 10 EXACT, velocity competitive)")

# sets.csv: replace the old 'CV (R2 video) ... UNRELIABLE' clause
rows = list(csv.DictReader(open(SETS))); cols = list(rows[0].keys())
for r in rows:
    if r["set_id"].startswith("20260616-BN-"):
        n = int(r["set_id"].split("-")[-1]); ar, sr, vo, vv = RES[n]
        note = r["notes"]
        cut = note.find(" CV (R2 video)")
        if cut != -1:
            note = note[:cut]
        note += (f" CV (R2 video, one-tap hub + confirmed deep-dish rim + transit_aware): reps_cv 10 "
                 f"EXACT (was AUTO 11 on BN-4/5 from the un/rerack; horizontal-aware merge + transit "
                 f"gate fixed it), conf 1.0. Abs MV RMSE {ar:.3f} vs Vitruve (SB {sr:.3f}); VL {vo}% "
                 f"vs Vit {vv}%. Across the 5: mean abs 0.040 ~ SB 0.039 (TIED; was a clear SB win - "
                 f"the scale was reading the 72px hub not the ~570px deep-dish rim). Watch IMU bench-"
                 f"gated still below target (RMSE 0.091, r 0.59 - detector over-segments paused/supine "
                 f"bench, the next gap).")
        r["notes"] = note
with open(SETS, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print("sets.csv updated")
print("DONE")
