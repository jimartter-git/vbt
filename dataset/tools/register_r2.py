#!/usr/bin/env python3
"""Register R2 video objects into the manifest under their CANONICAL set_id.

The R2 object key (what was uploaded) and the canonical set_id (what the DB/GT use) can
differ — a year typo (20240424 → 20260424), or a load-based remap (the 06-11 inclines:
videos 1/2/3 = the 155/155/175 sets = IB-2/IB-3/IB-4, since the 135 set wasn't filmed).
The manifest's `filename` (canonical, what cv_eval.CLIPS references) vs `key` (the real R2
object) columns decouple these, so `clip_store.resolve_clip` fetches the right object.

Downloads each object by key, probes resolution/fps/codec, hashes, appends/updates the
manifest row. Run `scripts/coverage.py` after to confirm the board is reconciled.
"""
from __future__ import annotations
import csv, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
REPO = os.path.dirname(DATASET)
sys.path.insert(0, os.path.join(REPO, "analysis"))
import av  # noqa: E402
import boto3  # noqa: E402

MAN = os.path.join(DATASET, "raw", "manifest.csv")
CACHE = os.path.join(DATASET, ".clipcache")
os.makedirs(CACHE, exist_ok=True)
MAN_COLS = ["filename", "set_id", "sha256", "bytes", "resolution", "fps", "codec",
            "duration_s", "url", "key", "note"]

# (R2 object key, canonical set_id, note). SQ-2-0604 omitted (camera fell — being deleted).
MAPPING = [
    ("20240424-BN-1.mov", "20260424-BN-1", "year typo 2024->2026; GT: SB/WL"),
    ("20240424-BN-2.mov", "20260424-BN-2", "year typo; NO GT yet"),
    ("20260527-SQ-1.mov", "20260527-SQ-1", "GT: Metric/SB/WL"),
    ("20260529-DL-1.mov", "20260529-DL-1", "top set; GT: stance/metric/SB/WL"),
    ("20260529-DL-2.mov", "20260529-DL-2", "backoff; NO GT yet"),
    ("20260529-DL-3.mov", "20260529-DL-3", "backoff; GT: stance/metric/SB/WL"),
    ("20260529-DL-4.mov", "20260529-DL-4", "backoff; NO GT yet"),
    ("20260602-BN-1.mov", "20260602-BN-1", "GT: SB/stance"),
    ("20260602-BN-2.mov", "20260602-BN-2", "GT: SB/vitruve"),
    ("20260602-BN-3.mov", "20260602-BN-3", "GT: SB/vitruve"),
    ("20260611-IB-1.mov", "20260611-IB-2", "155lb (video1->set IB-2; 135 set unfilmed)"),
    ("20260611-IB-2.mov", "20260611-IB-3", "155lb (video2->set IB-3)"),
    ("20260611-IB-3.mov", "20260611-IB-4", "175lb (video3->set IB-4, RPE8)"),
]

EP = os.environ.get("R2_ENDPOINT", "https://6747d02e809e8e72687bb909e5cf302a.r2.cloudflarestorage.com")
BUCKET = os.environ.get("R2_BUCKET", "vbt-video")


def probe(p):
    with av.open(p) as c:
        v = c.streams.video[0]
        return dict(resolution=f"{v.codec_context.width}x{v.codec_context.height}",
                    fps=round(float(v.average_rate), 2) if v.average_rate else "",
                    codec=v.codec_context.name,
                    duration_s=round(float(c.duration) / 1e6, 1) if c.duration else "")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    man = {}
    if os.path.exists(MAN):
        for r in csv.DictReader(open(MAN)):
            man[r["filename"]] = r
    s3 = boto3.client("s3", endpoint_url=EP, region_name="auto",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
    for key, sid, note in MAPPING:
        fn = f"{sid}.mov"
        dest = os.path.join(CACHE, fn)
        if not os.path.exists(dest):
            print(f"  downloading {key} -> {fn} ...", flush=True)
            s3.download_file(BUCKET, key, dest)
        info = probe(dest)
        row = dict(filename=fn, set_id=sid, sha256=sha256(dest),
                   bytes=os.path.getsize(dest), url="", key=key, note=note, **info)
        man[fn] = row
        print(f"  {fn:<20} {info['resolution']:<11} {info['fps']}fps  {row['bytes']//(1<<20)}MB  [{note}]")
    with open(MAN, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MAN_COLS); w.writeheader()
        for fn in sorted(man):
            w.writerow({c: man[fn].get(c, "") for c in MAN_COLS})
    print(f"\nmanifest now has {len(man)} clips. Next: add CLIPS entries + run coverage.py.")


if __name__ == "__main__":
    main()
