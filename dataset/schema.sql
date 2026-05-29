-- Personal multi-vendor VBT measurement database.
-- Source of truth = the CSVs in dataset/ (git-versioned, Sheets/chat-editable).
-- This SQLite file is a rebuilt ARTIFACT (gitignored) for fast queries/joins.
PRAGMA foreign_keys = ON;

-- One row per real physical set (the "comparable" anchor).
CREATE TABLE IF NOT EXISTS sets (
  set_id        TEXT PRIMARY KEY,   -- YYYYMMDD[session]-LIFT-N  e.g. 20260529-DL-1
  date          TEXT NOT NULL,
  lift          TEXT NOT NULL,      -- squat | bench | deadlift | ...
  load_kg       REAL,               -- canonical (always kg; dodges the WL kg/lb bug)
  load_entered  REAL,               -- as you logged it
  load_unit     TEXT,               -- lb | kg
  set_index     INTEGER,            -- nth set of this lift in the session
  target_reps   INTEGER,
  actual_reps   INTEGER,            -- YOUR ground-truth rep count
  rpe_actual    REAL,               -- YOUR subjective RPE -> the prior's training label
  notes         TEXT
);

-- Long/tidy: one row per (set, vendor, rep, metric). Gaps are free (no row).
CREATE TABLE IF NOT EXISTS rep_metrics (
  set_id      TEXT NOT NULL REFERENCES sets(set_id),
  vendor      TEXT NOT NULL,        -- vitruve|stance|smartbarbell|metric|wl_analysis|watch_imu|airpods_imu
  rep_index   INTEGER,              -- the vendor's OWN rep ordering (provenance)
  true_rep    INTEGER,              -- the PHYSICAL rep number (cross-vendor alignment key);
                                    -- equals rep_index unless a vendor mis/under-counts, then
                                    -- assert/infer the mapping. NULL = set-level.
  metric      TEXT NOT NULL,        -- mean_velocity|peak_velocity|rom|time_to_peak|ecc_power|concentric_time|...
  value       REAL,
  unit        TEXT,                 -- m/s | cm | s | W | % | count
  flag        TEXT,                 -- imputed|missed|phantom|low_confidence|set_avg_only
  confidence  REAL                  -- 0..1, optional
);
CREATE INDEX IF NOT EXISTS idx_rm_set    ON rep_metrics(set_id);
CREATE INDEX IF NOT EXISTS idx_rm_vendor ON rep_metrics(vendor);
CREATE INDEX IF NOT EXISTS idx_rm_metric ON rep_metrics(metric);
CREATE INDEX IF NOT EXISTS idx_rm_true   ON rep_metrics(true_rep);

-- Pointers to bulk time-series that don't belong in rows (WL per-frame txt,
-- watch ~200Hz, AirPods). Files live in dataset/raw/ (gitignored, local).
CREATE TABLE IF NOT EXISTS raw_files (
  set_id  TEXT NOT NULL REFERENCES sets(set_id),
  vendor  TEXT NOT NULL,
  path    TEXT NOT NULL,            -- relative to dataset/raw/
  kind    TEXT,                     -- perframe | imu100 | imu200 | video
  notes   TEXT
);
