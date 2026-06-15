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

-- ── CV training corpus ──────────────────────────────────────────────────────
-- The bytes live in R2 (docs/video-storage.md); these two tables are the
-- queryable metadata. A clip may have NO measured ground truth (set_id blank) —
-- it's still useful for CV training/robustness.

-- Storage/technical facts, one row per clip. Machine-filled by tools/ingest_clips.py
-- (PyAV/ffprobe). The repo's pointer into the R2 bucket.
CREATE TABLE IF NOT EXISTS clip_manifest (
  filename    TEXT PRIMARY KEY,     -- = the R2 object key, e.g. 20260614-DL-1.mov
  set_id      TEXT,                 -- links to a measured set if one exists, else blank
  sha256      TEXT,                 -- optional integrity check (resolve_clip verifies if set)
  bytes       INTEGER,
  resolution  TEXT,                 -- WxH, e.g. 1920x1080
  fps         REAL,
  codec       TEXT,                 -- h264 | hevc | ...
  duration_s  REAL,
  url         TEXT,                 -- optional public/presigned URL (else fetched by key)
  key         TEXT,                 -- R2 object key (defaults to filename)
  note        TEXT
);

-- Human annotations, one WIDE row per clip (edit in a spreadsheet). The CV-prefilled
-- columns (reps_cv/mean_vel_cv/cv_*) are DRAFT suggestions you verify/override.
-- Controlled vocab + ordinal scales: dataset/ANNOTATIONS.md.
CREATE TABLE IF NOT EXISTS clips (
  clip               TEXT PRIMARY KEY,  -- = clip_manifest.filename
  lift               TEXT,
  load_kg            REAL,
  load_unit          TEXT,
  gym                TEXT,
  equipment          TEXT,              -- bumper|iron_round|iron_hex|db|machine
  angle_kind         TEXT,              -- side|diagonal|head_on
  angle_quality      INTEGER,           -- 0..5 (higher = better for CV)
  background_clutter INTEGER,           -- 0..5 (higher = busier/noisier behind the bar)
  occlusion          INTEGER,           -- 0..5 (higher = more of the plate hidden)
  lighting           INTEGER,           -- 0..5 (higher = better lit)
  velocity_regime    TEXT,              -- normal|paused|speed_work|tempo_ecc|cluster|amrap
  tempo_notes        TEXT,              -- free text, e.g. "paused first+last rep"
  reps_cv            INTEGER,           -- DRAFT: provisional count from the auto CV path
  reps_true          INTEGER,           -- your verified count
  mean_vel_cv        REAL,              -- DRAFT: auto-path mean velocity (scale-suspect)
  cv_conf            REAL,              -- DRAFT: auto-path track confidence 0..1
  cv_flags           TEXT,              -- DRAFT: scale_suspect|static_seed|cv_error:...
  has_gt             TEXT,              -- true if a measured set_id is linked
  set_id             TEXT,              -- measured-set link (no FK: may precede filing)
  notes              TEXT
);
CREATE INDEX IF NOT EXISTS idx_clips_lift   ON clips(lift);
CREATE INDEX IF NOT EXISTS idx_clips_angle  ON clips(angle_kind);
CREATE INDEX IF NOT EXISTS idx_clips_regime ON clips(velocity_regime);
