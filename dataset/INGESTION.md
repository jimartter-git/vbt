# Ingestion playbook — turning a screenshot/export into a DB record

Goal: a fresh session can take a context-free screenshot or data file and file it
correctly into the dataset. Read `dataset/README.md` first for the data model
(`set_id`, `rep_metrics` long format, `true_rep`).

## Step 0 — collect metadata (always ask, never invent)

A measurement is useless unmatched. Get these from the user:

- **date** (YYYY-MM-DD)
- **lift** — squat | bench | deadlift | … (codes: SQ/BN/DL)
- **load** — value + unit (store canonical **kg**; convert lb→kg ×0.4536)
- **set #** that day for that lift → `set_index`
- **RPE** (optional but valuable — it's the prior's training label)
- **which other tools** recorded this *same physical set* (so they share a `set_id`)

Build `set_id = YYYYMMDD[session]-LIFT-N` e.g. `20260601-DL-2`.

## Step 1 — identify the vendor

| Vendor | How to recognize | Input form |
|---|---|---|
| **Stance** | dark UI, "Readiness 0.xx m/s", per-rep **Peak / Mean** table, "330lb 8 Reps" | screenshot |
| **SmartBarbell** | "Barbell Tracking" title, green bounding box on plate, table `Rep / Ascent / Descent / Pause / Velocity / ROM / Shift`, Y-axis bar-path plot | screenshot |
| **Metric** | green accents, "MEAN VELOCITY" pill, hexagons, rep table `M.vel / ROM / Ecc`; metric menu (time-to-peak, ecc power…) | screenshot |
| **WL Analysis** | spreadsheet-like per-**frame** table (`Frame, Time, velocity`) or red velocity-time graph; "Weight (lbs)" header | **.txt export** |
| **Vitruve** | (arriving) on-bar device app; per-rep mean/peak | CSV export |

## Step 2 — transcribe (screenshot) or import (file)

Append rows to `rep_metrics.csv`. Columns:
`set_id, vendor, rep_index, true_rep, metric, value, unit, flag, confidence`.

Metric vocabulary (normalize to these): `mean_velocity` (m/s), `peak_velocity`
(m/s), `rom` (cm), `concentric_time` (s), `eccentric_time` (s), `pause_time` (s),
`shift` (cm), `time_to_peak` (s), `ecc_power` (W), `mean_power` (W), `peak_power` (W).

`true_rep`: set equal to `rep_index` **unless** the vendor's rep count disagrees
with the true set and you can tell a rep was dropped — then map to the physical
rep number (and confirm with the user if ambiguous). `rep_index` blank +
`true_rep` blank = a **set-level** value.

### Per-vendor column → metric mapping

**Stance** — per rep: `Mean → mean_velocity (m/s)`, `Peak → peak_velocity (m/s)`.

**SmartBarbell** — per rep:
- `Velocity → mean_velocity (m/s)`
- `ROM → rom` — **convert m→cm** (0.60 → 60)
- `Ascent → concentric_time (s)`, `Descent → eccentric_time (s)`, `Pause → pause_time (s)`
- `Shift → shift` — convert m→cm
- **GOTCHA:** a trailing all-`0.00` row is a **phantom** (a dropped rep). Record it
  as `mean_velocity, value=0, flag=phantom, confidence=0`, with `true_rep` = the
  physical rep it failed to capture. Do NOT let it into stats.

**Metric** — per rep: `M.vel → mean_velocity`, `ROM → rom (cm)`, `Ecc → eccentric_time (s)`.
Optional extra screen: `T.to peak → time_to_peak (s)`, `B.pause → pause_time (s)`,
`Ecc power → ecc_power (W)`. **The "100%" LOAD/POWER/REPS/VELOCITY hexagons are
NOT measurement confidence** (likely plan/baseline adherence) — don't record them
as confidence.

**WL Analysis** — don't hand-type the per-frame table. Save the `.txt` into
`dataset/raw/`, add a `raw_files.csv` pointer, then:
`python tools/wl_import.py raw/<file>.txt <set_id> --append`
The importer selects columns **by name** (`velocity (vertical, m/s)`), so both the
slim 3-column and the rich ~16-column exports (velocity/accel/displacement/power/
force × axes) work in any order. It uses the **vertical velocity** channel for
segmentation, the **vertical displacement** channel for a direct drift-free ROM
(falls back to integrated velocity, flagged `rom_integrated`), and **vertical
acceleration** for per-rep `peak_accel`. Export at least vertical velocity; adding
displacement + acceleration is strictly better. **"Weight (lbs)" in the file is
actually kg — ignore it; use the user's stated load.** Verify the parser's rep
count against the user's true count the first time.
- **Non-round / 12-sided plates:** WL's automatic circle-detection fails (wrong
  scale → garbage weight cal, spurious velocity spikes, undercount). Fix in the WL
  app: **manually drag the circle inside the plate's straight edges AND toggle OFF
  "standard plate diameter."** That restored correct scale + velocities (verified
  on 20260424-BN-1). SmartBarbell's region-tracking handles non-round plates with
  no such step.

**Vitruve** — once it arrives, prefer its CSV export; it becomes the reference
vendor for calibration (`compare.py` auto-prefers it).

## Step 3 — file & verify

```bash
cd dataset
# (append rows to sets.csv + rep_metrics.csv, or run wl_import)
python tools/build_db.py            # rebuild sqlite
python tools/compare.py <set_id>    # sanity-check the cross-vendor table
```

Then commit & push (CSVs are source of truth; `dataset.sqlite` is gitignored).

## Rules (also enforced in compare.py)

1. Align across vendors on **`true_rep`**, never `rep_index`.
2. Velocity loss references the **best** rep (not rep 1) and is labelled with the
   rep it runs to; cross-vendor loss uses the **common window**.
3. Canonical units: load **kg**, ROM **cm**.
4. Flag non-measurements (`phantom`/`missed`) so they stay out of stats.
5. Derive metrics on the fly — never freeze a loss number that hides its window.
