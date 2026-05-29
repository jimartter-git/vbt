# Calibration Protocol — watch IMU vs Vitruve (deadlift)

Goal: collect synchronized wrist-IMU recordings and Vitruve ground truth across
a range of bar velocities so we can (a) quantify watch error and (b) fit a
correction back into the estimator.

## Why deadlift first

Wrist tracks the bar tightly, motion is near-1D vertical, and there are clean
zero-velocity points at the floor and at lockout — the best case for ZUPT and
the easiest signal to trust before tackling harder lifts.

## Equipment

- Apple Watch (Series 8 / SE2 / Ultra+) running the VBT watch app.
- Vitruve attached to the bar per its instructions (ground truth: per-rep mean &
  peak velocity, ROM).
- A barbell + plates; a load you can move across a velocity range.

## Time sync — do NOT over-engineer it

You do **not** need sub-millisecond clock alignment. You need **rep-to-rep
correspondence**: both devices count the same reps, so watch rep *i* ↔ Vitruve
rep *i*.

- Primary alignment: **rep index**.
- Safety anchor: before each set, give the loaded bar **3 sharp taps** (or a
  firm rack tap) to plant a recognizable acceleration spike at the start of the
  watch recording. This anchors the sequence and exposes any dropped/extra rep.
- Only fall back to cross-correlation of velocity profiles if per-rep indexing
  is ever ambiguous.

## Session structure

Run a structured grid so you get a regression, not a single point:

| Block | Load (% 1RM) | Sets | Reps/set | Intent          |
|-------|--------------|------|----------|-----------------|
| A     | ~50%         | 2    | 3        | fast / high vel |
| B     | ~70%         | 2    | 3        | moderate        |
| C     | ~85%         | 2    | 2–3      | grindy / low vel|

Per rep, the watch app records one CSV (+ JSON sidecar). Log the matching
Vitruve mean/peak velocity + ROM per rep (export or photo the Vitruve summary).
Repeat the whole grid on ≥2 separate days to capture session-to-session
variation (attachment, fatigue, watch position).

## During capture

- Start the watch workout BEFORE the first rep; confirm the live sample-rate
  readout sits near 200 Hz (catches throttling early).
- Keep the watch in a consistent wrist position across reps.
- Note load, set #, and RPE in the session notes field.
- Watch the battery/thermal state across the full session — sustained 200 Hz +
  workout session is the riskiest infra cost to validate.

## Analysis & metrics (see `analysis/`)

Feed CSVs through the pipeline and align to Vitruve by rep index, then report:

- **Rep-count accuracy** — precision / recall vs Vitruve rep count.
- **Mean-velocity error** — bias + RMSE (watch vs Vitruve), per load block.
- **Velocity-loss correlation** — does the watch's intra-set velocity-loss curve
  track Vitruve's? (This matters more than absolute velocity.)
- **ROM error** — secondary; expected to be worse than velocity.
- **Plots** — watch-vs-Vitruve scatter + regression, and a Bland-Altman plot.

Output of calibration = regression coefficients to fold back into the estimator,
plus a go/no-go read on whether the wrist signal is good enough for deadlift.
