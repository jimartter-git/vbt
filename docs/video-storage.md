# Video storage — dev phase (and where it goes live)

HD masters are too big for git (GitHub blocks >100 MB; a 1080p60 clip is
~60–130 MB). So **the bytes live in Cloudflare R2; the repo keeps only a
pointer.** The CV board downloads a master on demand and caches it locally. This
is a small-scale rehearsal of the live-app rule: **keep the metrics forever,
treat the video as remote/disposable.**

## The pieces

| Piece | Where | What |
|---|---|---|
| **Masters** | R2 bucket `vbt-video` | the raw `.mov`/`.mp4`, one object per clip, key = filename |
| **Pointer** | `dataset/raw/manifest.csv` (committed) | `filename → set_id, sha256, bytes, resolution, fps, codec, duration_s, url, key, note` |
| **Resolver** | `analysis/vbt_video/clip_store.py` | `resolve_clip()`: local file → cache → download from R2 |
| **Cache** | `dataset/.clipcache/` (gitignored) | downloaded masters, reused across runs |

Small legacy clips (the 440px web clips) stay committed and resolve instantly —
nothing about the existing board changes. Only **new HD masters** go to R2.

R2 config (non-secret — account id is in every URL):
- Endpoint: `https://6747d02e809e8e72687bb909e5cf302a.r2.cloudflarestorage.com`
- Bucket: `vbt-video`

Override via env: `R2_ENDPOINT`, `R2_BUCKET`. **Credentials are secrets** and never
go in git: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (set as environment secrets
when a session needs to *download* a private master — make a **read-only** token
for that, separate from the phone's read-write upload token).

## Registering a new clip (the workflow)

1. **Upload the master to R2** (see upload options below). Object key = the
   filename, e.g. `20260611-IB-3.mov`.
2. **Add a manifest row.** From the iPhone Photos info panel you already have
   resolution / fps / codec / bytes (that screenshot is enough). `sha256` is
   optional — if present the resolver verifies the download; blank = skip.
3. **Register in `cv_eval.py` `CLIPS`** as usual (path stays `dataset/raw/<file>`;
   the resolver maps it to R2 transparently). Score on its own HD track — HD does
   **not** go on the apples-to-apples low-fi board (cv-fusion learning #14).

To let a fresh container fetch a private master, export the read-only creds and
run the board normally; `resolve_clip()` downloads to `dataset/.clipcache/` once.

## Running the CV pass on R2 clips (the corpus enrichment)

Once a batch is uploaded + manifested, a CV-equipped session fills the technical
metadata and the provisional rep count straight from R2:

```bash
# 1. read-only R2 creds in the environment (env vars, never committed):
#    R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY   (endpoint/bucket have defaults)
# 2. deps: pip install boto3  +  the CV stack (analysis/requirements.txt: PyAV, OpenCV)
# 3. pull every manifest clip from R2, probe it, run the seed-free CV count:
python dataset/tools/ingest_clips.py --from-manifest --sha
python dataset/tools/build_db.py
```

`--from-manifest` resolves each clip (download → `dataset/.clipcache/`), runs
`ffprobe`/PyAV for codec/duration, and the shipped AUTO estimator for a draft
`reps_cv`, upserting into `manifest.csv` + `clips.csv` (existing human annotations
preserved). It's idempotent — re-run adds only new/unenriched clips (`--force` to
redo). Then **score against ground truth**: `reps_cv` vs `reps_true` (the filed
Vitruve count) is the count check; for velocity, add the clip to `cv_eval.py`
`CLIPS` on its **HD track** (not the low-fi aggregate board — learning #14) or use
`vel_eval.py`. Keep the masters off the default `cv_eval --auto` run so a bare
board doesn't pull gigabytes.

## Uploading from phone / iPad

R2 has no consumer upload app and does **no** transcoding — bytes are stored
as-is. Two tiers:

### Tier 1 — works today, zero code (Safari)
R2 dashboard → bucket `vbt-video` → **Upload**. Drag the clip in from Files/Photos
on iPad. Fine for occasional clips; dashboard uploads cap at a few hundred MB
(your clips fit). Then send me the filename + Photos-panel metadata to file the
manifest row.

### Tier 2 — one tap from the share sheet (Worker + Shortcut)
The clean "share → compressed → in the bucket" path. Signing S3 requests inside
Shortcuts is painful, so put a tiny **Cloudflare Worker** in front as an
authenticated upload proxy (Workers free tier = 100k req/day):

```js
// Worker bound to the R2 bucket as `BUCKET`; secret UPLOAD_TOKEN set in dashboard.
export default {
  async fetch(req, env) {
    if (req.method !== "PUT") return new Response("PUT only", { status: 405 });
    if (req.headers.get("authorization") !== `Bearer ${env.UPLOAD_TOKEN}`)
      return new Response("unauthorized", { status: 401 });
    const key = new URL(req.url).pathname.slice(1);   // /<filename>
    if (!key) return new Response("missing key", { status: 400 });
    await env.BUCKET.put(key, req.body, {
      httpMetadata: { contentType: req.headers.get("content-type") || "video/quicktime" },
    });
    return new Response(`ok ${key}\n`, { status: 200 });
  },
};
```

**iOS Shortcut** (Shortcuts app → new shortcut, "Show in Share Sheet" on, accepts
Media):
1. **Receive** what's shared (the video).
2. *(optional compress)* **Encode Media** → smaller size / 720p — halves or better.
3. **Get Name** of the media → that's `<filename>`.
4. **Get Contents of URL**:
   - URL: `https://<your-worker-subdomain>.workers.dev/<filename>`
   - Method: **PUT**
   - Request Body: **File** (the encoded media)
   - Headers: `Authorization: Bearer <UPLOAD_TOKEN>`,
     `Content-Type: video/quicktime`
5. Run it from the Photos share sheet — one tap, clip lands in `vbt-video`.

Keep the upload (Worker) token separate from the container's read-only token, so a
leak from the phone can't read or delete the bucket.

## Capture settings that help before any of this
- **HEVC** (Settings → Camera → Formats → High Efficiency) ≈ halves the file at
  the source, no CV-relevant loss. Biggest free win.
- **1080p60** is good for CV: 60 fps sharpens turnaround velocity, 1080p helps the
  open absolute-m/s / plate-sizer problem (cv-fusion roadmap #2).

## Live app (the direction, not built here)
Different solution, same principle. Run CV **on-device**; sync the kilobyte-scale
metrics (the `VelocitySource` output). Video stays on-device by default; upload is
**opt-in** (cloud backup, or consented model-training data → exactly this dataset).
Anything uploaded is compressed to a 720p proxy. Metrics persist forever; masters
expire via storage lifecycle. R2-for-masters + metrics-in-DB here is the rehearsal.
