# Clip annotations — controlled vocabulary

The CV-training corpus is `dataset/clips.csv` (one **wide** row per clip, edited in
a spreadsheet). The bytes live in R2; `dataset/raw/manifest.csv` is the storage
pointer. Keep labels consistent using the vocab below so SQLite queries
(`build_db.py`) return clean training cohorts.

## Workflow
1. Upload masters to R2 (`rclone copyto … r2:vbt-video/<name>.mov`).
2. `python dataset/tools/ingest_clips.py <folder>` — fills `manifest.csv`
   (technical) + a **draft** `clips.csv` row, CV-prefilled with `reps_cv` and a
   rough `velocity_regime` hint.
3. Open `dataset/clips.csv` in Numbers/Sheets, fill the subjective columns,
   verify `reps_cv` → `reps_true`. Commit.
4. `python dataset/tools/build_db.py` → query in SQLite.

`clip` is the join key everywhere (= the R2 filename). Don't rename a clip without
also renaming the R2 object (`rclone moveto`).

## Columns & scales

| Column | Type | Meaning |
|---|---|---|
| `clip` | filename | = R2 object key, e.g. `20260614-DL-1.mov` |
| `lift` | enum | squat · bench · deadlift · incline_bench · romanian_deadlift · row · ohp · accessory |
| `load_kg` / `load_unit` | num / enum | canonical kg; `load_unit` = lb\|kg as entered |
| `gym` | text | e.g. Equinox, Westwood, travel |
| `equipment` | enum | bumper · iron_round · iron_hex · db · machine |
| `angle_kind` | enum | **side** · **diagonal** · **head_on** (drives px→m scale — see learning #10) |
| `angle_quality` | 0–5 | how clean the view is for CV (5 = textbook side-on, plate fully visible) |
| `background_clutter` | 0–5 | busyness behind the bar (0 = blank wall, 5 = mirror + rack + people) |
| `occlusion` | 0–5 | how much the working plate is hidden (0 = never, 5 = mostly blocked) |
| `lighting` | 0–5 | exposure quality (0 = dark/backlit, 5 = bright even light) |
| `velocity_regime` | enum | **normal** · **paused** · **speed_work** · **tempo_ecc** · **cluster** · **amrap** |
| `tempo_notes` | text | free, e.g. "paused first+last rep", "1s pause every rep" |
| `reps_cv` | int | DRAFT auto-path count (verify) |
| `reps_true` | int | your verified count |
| `mean_vel_cv` / `cv_conf` / `cv_flags` | — | DRAFT auto-path outputs; `cv_flags` ∈ scale_suspect\|static_seed\|cv_error:… |
| `has_gt` / `set_id` | bool / id | `true` + `set_id` when a measured set (Vitruve/SB) is linked |
| `notes` | text | anything else |

### Ordinal 0–5 convention
Higher = **better/more** of the named quality, except `background_clutter` and
`occlusion` where higher = **worse** (more clutter / more hidden). Score what *you*
see; these are subjective human labels, not measurements — that honesty is the point
(they train/stress the CV, they don't validate it).

### `velocity_regime`
- **normal** — straight work set, lower with no deliberate tempo manipulation.
- **paused** — a held pause at a position (e.g. paused bench/squat).
- **speed_work** — dynamic-effort: submaximal load moved fast, stop short of fatigue.
- **tempo_ecc** — slow controlled eccentric.
- **cluster** — intra-set rest between reps/mini-sets.
- **amrap** — taken to or near failure.

The ingest script's `*?` suffix (`normal?`, `speed_work?`) means a low-confidence
machine guess — replace with the clean value when you review.

## Why this lives in git, not R2
R2 stores objects, not queryable fields. Git CSVs are versioned, diff-able, and
join into SQLite — the same split the live app uses (metrics in a DB, video in
object storage). See `docs/video-storage.md`.
