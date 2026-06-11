"""Resolve a dataset clip path to a usable local file, fetching from Cloudflare
R2 on demand when the master isn't committed in the repo.

Why this exists
---------------
HD masters (1080p60 ≈ 60–130 MB) are too large for git — GitHub blocks >100 MB
and clones bloat fast. So masters live in an R2 bucket; the repo keeps only
`dataset/raw/manifest.csv` (filename -> remote object + checksum + metadata).
`cv_eval.py` asks this module for a usable path: small legacy clips that ARE
committed resolve instantly; HD masters download once to a gitignored cache
(`dataset/.clipcache/`) and are reused thereafter. Same principle as the live
app — keep the metrics, treat the video as remote/disposable.

No hard dependency
------------------
- A public/presigned `url` in the manifest downloads via urllib (stdlib only).
- A private-bucket fetch uses boto3 (S3-compatible) with env credentials:
    R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY   (SECRETS — never commit)
    R2_ENDPOINT, R2_BUCKET                    (non-secret; defaults below)
  boto3 is imported lazily, so the board runs fine without it as long as the
  clips it needs are already local.
"""
from __future__ import annotations

import csv
import hashlib
import os
import urllib.request

# Non-secret config (account id is exposed in every URL — safe to commit). Env wins.
R2_ENDPOINT = os.environ.get(
    "R2_ENDPOINT", "https://6747d02e809e8e72687bb909e5cf302a.r2.cloudflarestorage.com")
R2_BUCKET = os.environ.get("R2_BUCKET", "vbt-video")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cache_dir(repo: str) -> str:
    d = os.path.join(repo, "dataset", ".clipcache")
    os.makedirs(d, exist_ok=True)
    return d


def _load_manifest(repo: str) -> dict:
    p = os.path.join(repo, "dataset", "raw", "manifest.csv")
    if not os.path.exists(p):
        return {}
    rows = {}
    with open(p, newline="") as f:
        for r in csv.DictReader(f):
            fn = (r.get("filename") or "").strip()
            if fn:
                rows[fn] = r
    return rows


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _verify(path: str, row: dict) -> None:
    want = (row.get("sha256") or "").strip()
    if want and _sha256(path) != want:
        raise ValueError(
            f"sha256 mismatch for {os.path.basename(path)} "
            f"(manifest expects {want[:12]}…) — re-download or fix the manifest.")


def _download_url(url: str, dest: str) -> None:
    tmp = dest + ".part"
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 (trusted manifest URL)
    os.replace(tmp, dest)


def _download_s3(key: str, dest: str) -> None:
    try:
        import boto3  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Fetching a private R2 object needs boto3 (`pip install boto3`), or add a "
            "public/presigned `url` to the manifest row.") from e
    ak = os.environ.get("R2_ACCESS_KEY_ID")
    sk = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not (ak and sk):
        raise RuntimeError(
            "R2 credentials missing: export R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY "
            "(or add a public `url` to the manifest row).")
    s3 = boto3.client(
        "s3", endpoint_url=R2_ENDPOINT, aws_access_key_id=ak,
        aws_secret_access_key=sk, region_name="auto")
    tmp = dest + ".part"
    s3.download_file(R2_BUCKET, key, tmp)
    os.replace(tmp, dest)


def resolve_clip(path: str, repo: str | None = None) -> str:
    """Return a local filesystem path for ``path`` (repo-relative or absolute).

    Order: committed local file -> cached download -> fetch from R2 (url or
    private key) into the gitignored cache. Raises a clear error if the clip is
    neither local nor in the manifest.
    """
    repo = repo or _repo_root()
    local = path if os.path.isabs(path) else os.path.join(repo, path)
    if os.path.exists(local):
        return local

    fn = os.path.basename(local)
    row = _load_manifest(repo).get(fn)
    if row is None:
        raise FileNotFoundError(
            f"{fn} is not committed locally and has no dataset/raw/manifest.csv entry. "
            f"Upload the master to R2 and add a manifest row (see docs/video-storage.md).")

    dest = os.path.join(_cache_dir(repo), fn)
    if os.path.exists(dest):
        _verify(dest, row)
        return dest

    url = (row.get("url") or "").strip()
    key = (row.get("key") or fn).strip()
    if url:
        _download_url(url, dest)
    else:
        _download_s3(key, dest)
    _verify(dest, row)
    return dest
