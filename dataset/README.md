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
| `rep_metrics.csv` | one row per (set, vendor, rep, metric) | long/tidy — gaps are free; `flag` carries imputed/missed/phantom/low_confidence. Two rep keys: `rep_index` (vendor's own count) + `true_rep` (physical rep — the alignment key) |
| `raw_files.csv` | pointers | to bulk time-series in `raw/` (WL txt, watch/AirPods) |
| `clips.csv` | one wide row per CV-corpus clip | human annotations (angle/clutter/regime…) + CV-prefilled draft count; edit in a spreadsheet. Vocab: `ANNOTATIONS.md`. Bytes live in R2 |
| `raw/manifest.csv` | one row per clip | storage pointer (sha/bytes/res/fps/codec + R2 key); machine-filled by `tools/ingest_clips.py`. See `../docs/video-storage.md` |
| `priors/{lift}_rpe_velocity.csv` | per RPE | your hand-built velocity→RPE curves (hardcode/min/avg/max), **SmartBarbell-frame** |
| `schema.sql` | — | SQLite DDL (the DB is a rebuilt artifact, gitignored) |

Vendors: `vitruve · stance · smartbarbell · metric · wl_analysis · watch_imu · airpods_imu`.
Adding the watch/AirPods later is purely additive — they're just more vendors,
and their per-rep summaries land in `rep_metrics.csv` alongside the commercial
devices (your `VelocitySource` contract, realized as data).

## Rep identity & robust derived metrics

Two rep numberings, deliberately kept separate:

- **`rep_index`** — the k-th rep *as that vendor counted it* (provenance).
- **`true_rep`** — the **physical** rep number. This is the cross-vendor key.
  It equals `rep_index` *unless* a vendor mis/under-counts; if a vendor drops a
  **middle** rep, its `rep_index` shifts but `true_rep` stays anchored to the
  real sequence (assert/infer the mapping — same problem as fusion alignment).

Consequence: a vendor that captured only 7 of 8 reps simply has **no
`true_rep = 8` row** — correctly housed among 8-rep sets, never masquerading as
comparable on rep 8.

Rules for any calculated measure (enforced in `compare.py`):
1. **Align on `true_rep`**, never `rep_index`, across vendors.
2. **Reference the *best* rep, not rep 1** (warm-in often makes rep 2–3 fastest).
3. **State the window.** Velocity loss is labelled with the rep it runs to, and a
   **common-window** version (reps every vendor observed) gives apples-to-apples
   cross-vendor comparison.
4. **Derive on the fly** from the per-rep rows — never freeze a loss number that
   hides which reps it used.

## Entry workflow (multimodal in, normalized out)

> **Adding a record from a screenshot/export?** Follow `INGESTION.md` — it has the
> per-vendor recognition + column→metric recipes and the metadata to collect.

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
