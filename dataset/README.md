# Personal multi-vendor VBT measurement database

A living database that records the **same set, measured by multiple tools**, so
we can quantify agreement, build a velocity-dependent (or constant-offset)
calibration, and seed the app's per-user prior. It's a personal research log
first; the app consumes its *findings*, not the DB itself.

## The linchpin: `set_id`

Every tool measuring one physical set shares one ID, so we always know what's
comparable:

```
YYYYMMDD[session]-LIFT-N      e.g.  20260529-DL-1   (1st deadlift set, May 29)
                                    20260601b-SQ-3  (3rd squat set, 2nd session)
```

Lift codes: `SQ` squat · `BN` bench · `DL` deadlift (extend as needed).

## Files (source of truth = these CSVs, git-versioned)

| File | Grain | Notes |
|---|---|---|
| `sets.csv` | one row per real set | date, lift, load (kg canonical + as-entered), your rep count + **subjective RPE** (the prior's label) |
| `rep_metrics.csv` | one row per (set, vendor, rep, metric) | long/tidy — gaps are free; `rep_index` blank = set-level; `flag` carries imputed/missed/phantom/low_confidence |
| `raw_files.csv` | pointers | to bulk time-series in `raw/` (WL txt, watch/AirPods) |
| `priors/{lift}_rpe_velocity.csv` | per RPE | your hand-built velocity→RPE curves (hardcode/min/avg/max), **SmartBarbell-frame** |
| `schema.sql` | — | SQLite DDL (the DB is a rebuilt artifact, gitignored) |

Vendors: `vitruve · stance · smartbarbell · metric · wl_analysis · watch_imu · airpods_imu`.
Adding the watch/AirPods later is purely additive — they're just more vendors,
and their per-rep summaries land in `rep_metrics.csv` alongside the commercial
devices (your `VelocitySource` contract, realized as data).

## Entry workflow (multimodal in, normalized out)

You supply linking metadata per set; inputs arrive however each tool allows:

1. **Metadata** — for each set, confirm: `set_id | lift | load | RPE | which vendors`.
   Paste it in chat (or a Sheets row) so values get matched correctly.
2. **Screenshot-only apps** (Stance, SmartBarbell, Metric) — transcribed by hand
   (you/me/an agent) into `rep_metrics.csv`.
3. **Exports** — WL `.txt` → `tools/wl_import.py`; Vitruve CSV → (importer TBD when
   it arrives). Drop the file in `raw/`, run the importer, tagged with the set_id.
4. **Raw IMU** (later) — watch/AirPods CSV in `raw/`, summaries derived into rows.

Units are canonicalized on entry (load in **kg**; ROM in **cm**) — this dodges the
WL "lbs that's actually kg" mislabel.

## Tools

```bash
pip install -r ../analysis/requirements.txt        # pandas/scipy/numpy

python tools/seed_first_record.py     # bootstrap record #1 (330x8 deadlift) — idempotent
python tools/build_db.py              # rebuild dataset.sqlite from the CSVs
python tools/compare.py 20260529-DL-1 # cross-vendor table + agreement vs reference
python tools/wl_import.py raw/<file>.txt <set_id> [--append]   # WL per-frame -> rep rows
```

`compare.py` prints the per-rep table across vendors, a per-vendor summary
(mean / best / velocity-loss), and bias/RMSE vs a reference vendor (Vitruve when
present, else Stance). That last block is the calibration signal — a roughly
constant bias across vendors supports the simple offset calibration.

## How it seeds the app

- `priors/*.csv` → cold-start for the per-user `MovementPrior` (velocity→RPE),
  refined over time and re-expressed per source frame.
- per-vendor bias from `compare.py` aggregated across sets → the calibration that
  maps any source into the reference (Vitruve) frame.
- `sets.rpe_actual` vs terminal velocity → trains/validates the RPE model.

## Record #1 (seeded)

`20260529-DL-1` — deadlift 330 lb × 8, measured by Stance, SmartBarbell, Metric
(per-rep) and WL Analysis (set average). The set where SmartBarbell dropped the
last rep — our first real cross-vendor divergence and the fusion test fixture.
