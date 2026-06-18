# Overnight goal prompt — seed-free CV plate localization (classical)

> Paste the block below into a fresh session to make unsupervised overnight progress.
> Context as of 2026-06-18: Tracks A/B/C landed; watch velocity at target (calibrated
> RMSE 0.070); watch app now captures gyro/mag (first-build flagged). The CV plate
> **detector** is scaffolded but proven **DATA-limited, not compute-limited**: a 50-epoch
> CPU train (stopped at 15 — flat held-out mAP ~0.22, no upward trend) blind-evals to
> DL-2 10/10 (bumper, beats heuristic), BN-2 1/10 (dark iron), SQ-4 0/10 (hex). So the
> night is for CLASSICAL localization, not training.

```
GOAL: Overnight, harden VBT's SEED-FREE CV plate localization so the no-tap (zero-config)
rep counts on the MAIN lifts approach the tap-path counts BLIND — especially dark iron and
hex, where seed-free currently under-counts (e.g. ROW-2-0608 reads 5/10). This is the named
classical follow-up from CLAUDE.md learnings #27/#28 and docs/classical-foundation.md. The
detector is DATA-limited, not compute-limited (a 50-epoch CPU train showed flat held-out
mAP) — so DO NOT spend the night training models. Exhaust the CLASSICAL working-plate
localization first.

START (every run):
1. Sync per CLAUDE.md branch protocol: `git fetch origin --prune`, fast-forward the working
   branch `claude/classical-foundation-guardrail-iu77ma`. Develop and push ONLY there.
2. Setup: `python -m venv analysis/.venv && . analysis/.venv/bin/activate && pip install -r
   analysis/requirements.txt -r analysis/requirements-video.txt`. Confirm `pytest` under
   analysis/ is green BEFORE changing anything. (Do NOT install requirements-ml.txt — no ML
   tonight; it clobbers opencv-contrib.)
3. Read docs/classical-foundation.md (incl. its Status checklist) and CLAUDE.md learnings
   #10-#27 + #12 (seed the WORKING plate). Then `git log --oneline -15`.

PRIMARY WORK — classical working-plate localization (in vbt_video/track.py
`seed_candidates` and the auto path `pipeline._estimate_auto`):
- Strengthen candidate GENERATION + RANKING with working-plate PRIORS so the bar plate wins
  over rack/mirror/decoy circles WITHOUT any per-clip config: (a) prefer candidates whose
  flow track passes the no-GT honesty checks (vbt_video/honesty.py) — vertical-dominant,
  periodic, moving; (b) two plates that translate TOGETHER (left/right of the bar) are the
  bar, a lone rack disc is not; (c) position priors (bench/squat plate near the hands/mid-
  frame, deadlift near the floor) used as a SOFT prior, never a hard gate; (d) dark-iron
  recall — the HoughCircles seeder misses low-contrast iron, so add a motion/blob fallback
  that proposes dark moving discs (still verified by flow + honesty, so a bad proposal can't
  win).
- Keep the honesty GATE: every reported seed-free count must be backed by a track that
  passes honesty. A track can be honest yet under-count (segmentation) — that's fine; the
  goal is honest counts that are also CORRECT on the main lifts.

HARD RULES (the guardrail — do not violate):
- Measure BLIND only. The headline is the seed-free `auto` path (seed=None, no per-clip
  hint). Registered CLIPS seeds/rims are simulated-tap/oracle — never the headline.
- NO REGRESSION: before/after EVERY detector change, diff the WHOLE local corpus with
  `python analysis/scripts/_trackc_check.py` (zero flips that worsen a main-lift count) AND
  `python analysis/scripts/cv_eval.py --auto`. A main-lift regression is the line you don't
  cross (learning #15). If a change only wins in-sample / on one clip, SAY SO and don't ship
  it as progress.
- ONE parameter set across all lifts/clips. Per-clip or per-lift knobs are the overfit.
- Don't re-litigate rejected non-levers (learnings #11, #13, #14, #20). Don't open PRs.
- Local clips only (R2 network is unreliable); the ~26 local .mov/.mp4 are enough.

VALIDATE + CADENCE:
- Add/extend tests for any new localization behavior; keep `pytest` green.
- Commit + push to the working branch at EVERY validated checkpoint (ephemeral container =
  unpushed work is lost). Use small, well-described commits.
- When something lands blind with no regression: update the Status checklist in
  docs/classical-foundation.md and add/extend a CLAUDE.md learning with the BLIND numbers.

IF PRIMARY IS BLOCKED OR DONE, fall back (in order), same discipline:
1. Finish the full blind board: get `cv_eval.py --guardrail` to complete on the LOCAL clips
   (skip R2) and record the honest seed-free vs sim-tap aggregate + blind-in-sample delta in
   docs/cv-fusion.md.
2. The 2 watch wave-segmenter count misses (ROW-3 -1, SQ-3 +1) — ONLY a structurally
   principled fix that holds under leave-one-session-out (`wave_eval.py --blind`); if the
   only fix trades one main-lift miss for another, leave it and document why.
3. Test/doc hardening: make sure docs + CLAUDE.md reflect reality.

DO NOT: train ML models (data-limited; CPU = hours for nothing); chase absolute-velocity
scale or watch orientation (proven non-levers this session); overfit to the 26 clips.

END STATE: seed-free main-lift counts improved BLIND with zero main-lift regression and
every count backed by an honest track; or a clear, documented finding that the classical
ceiling is reached and the remaining gap is genuinely data/appearance-limited (dark iron /
hex) — which itself justifies the learned detector when more data exists. Plan doc + CLAUDE.md
reflect reality.
```
