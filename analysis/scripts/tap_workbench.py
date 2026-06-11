#!/usr/bin/env python3
"""Tap workbench — the human-grade tap loop, as tooling (2026-06-11).

The loop that took the LLM-tap experiment from 'right object, wrong pixels' to
verified dead-on plate tracks on every trackable clip:

    1. SEE MOTION   python analysis/scripts/tap_workbench.py motion CLIP T
                    (frame + |diff| heatmap around T: the working plate lights up,
                     stored plates / mirrors / bystanders stay dark)
    2. SCRUB        ... scrub CLIP T1 T2 ...     (find a SHARP frame: seed at a
                     lockout/turnaround PAUSE — mid-rep motion blur gives flow bad
                     corners and was the root cause of several failed taps)
    3. ZOOM         ... zoom CLIP T X0 Y0 X1 Y1  (2x crop, orig-px grid, to place
                     the box precisely; on dark iron make it TIGHT on the textured
                     hub/logo and EXCLUDE static background — background corners
                     outvote a textureless plate)
    4. TAP + VERIFY ... tap CLIP X Y W H TSEED   (tap-on-ANY-frame: bidirectional
                     flow + relative gate + plausibility gate; prints the rep table
                     and renders a 6-frame tracked-overlay strip — LOOK at it; the
                     track must visibly ride the plate the whole set, else re-tap)

Outputs land in /tmp/tapwb/. See docs/cv-fusion.md "human-grade" section for the
validated lessons this encodes.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from vbt_video import VideoConfig, VideoVelocitySource  # noqa: E402
from vbt_video.frames import PyAVDecoder  # noqa: E402
from vbt_video.track import ReplaySource, FlowTracker, track_bidirectional  # noqa: E402

OUT = "/tmp/tapwb"


def _grid(im, step=50, x_off=0, y_off=0, zoom=1):
    h, w = im.shape[:2]
    for x in range(0, w, step):
        cv2.line(im, (x, 0), (x, h), (255, 255, 0), 1)
        if x % (2 * step) == 0:
            cv2.putText(im, str(x_off + x // zoom), (x + 2, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    for y in range(0, h, step):
        cv2.line(im, (0, y), (w, y), (255, 255, 0), 1)
        if y % (2 * step) == 0:
            cv2.putText(im, str(y_off + y // zoom), (2, y + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    return im


def _frame_at(rep, t):
    tt = rep.nearest_time(t)
    for f in rep:
        if abs(f.t - tt) < 1e-6:
            return f.t, f.img
    raise ValueError(f"no frame near t={t}")


def _save(name, img):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    cv2.imwrite(p, img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(p)


def cmd_motion(clip, t):
    rep = ReplaySource(PyAVDecoder(clip))
    ts = sorted(set(rep.nearest_time(t + dt) for dt in (-0.5, -0.3, -0.15, 0, 0.15, 0.3, 0.5)))
    grays = {}
    for f in rep:
        if any(abs(f.t - x) < 1e-6 for x in ts):
            grays[round(f.t, 4)] = cv2.cvtColor(f.img, cv2.COLOR_BGR2GRAY)
    keys = sorted(grays)
    M = np.zeros_like(grays[keys[0]], np.float32)
    for a, b in zip(keys, keys[1:]):
        M += cv2.absdiff(grays[a], grays[b]).astype(np.float32)
    M = cv2.GaussianBlur(M, (9, 9), 0)
    M = (255 * M / max(1e-6, M.max())).astype(np.uint8)
    _, base = _frame_at(rep, t)
    overlay = cv2.addWeighted(base, 0.55, cv2.applyColorMap(M, cv2.COLORMAP_JET), 0.45, 0)
    _save(f"motion-{t}.jpg", np.hstack([_grid(base.copy()), _grid(overlay)]))


def cmd_scrub(clip, times, crop=None):
    rep = ReplaySource(PyAVDecoder(clip))
    tiles = []
    for t in times:
        tt, im = _frame_at(rep, t)
        if crop:
            x0, y0, x1, y1 = crop
            im = im[y0:y1, x0:x1]
        im = im.copy()
        cv2.putText(im, f"t={tt:.2f}", (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        tiles.append(im)
    _save("scrub.jpg", np.hstack(tiles))


def cmd_zoom(clip, t, x0, y0, x1, y1):
    rep = ReplaySource(PyAVDecoder(clip))
    _, im = _frame_at(rep, t)
    c = cv2.resize(im[y0:y1, x0:x1], ((x1 - x0) * 2, (y1 - y0) * 2))
    _save(f"zoom-{t}.jpg", _grid(c, x_off=x0, y_off=y0, zoom=2))


def cmd_tap(clip, x, y, w, h, tseed):
    rep = ReplaySource(PyAVDecoder(clip))
    cfg = VideoConfig(tracker="flow", rep_gate="relative", ellipse_scale=True,
                      plausibility_gate=True)
    reps, meta = VideoVelocitySource(cfg).estimate(rep, seed_bbox=(x, y, w, h), seed_time=tseed)
    print(f"tap=({x},{y},{w},{h})@{tseed}s -> n={len(reps)} conf={meta['track_confidence']} "
          f"static={meta['static_track_suspect']} y_span={meta['y_span_px']}")
    for r in reps:
        print(f"  r{r['rep_index']:>2} t={r['t']:>6.2f} mv={r['mean_velocity']:>5.2f} "
              f"rom={r['rom']:>6.1f} {r.get('flag', '')}")
    tr = track_bidirectional(rep, (x, y, w, h), tseed, lambda: FlowTracker(ellipse_scale=True))
    seed_t = rep.nearest_time(tseed)
    tiles = []
    for fc in (0.02, 0.2, 0.4, 0.6, 0.8, 0.97):
        ft = rep.nearest_time(fc * tr.traj[-1, 0])
        _, im = _frame_at(rep, ft)
        im = im.copy()
        j = int(np.argmin(np.abs(tr.traj[:, 0] - ft)))
        cx, cy = int(tr.traj[j, 1]), int(tr.traj[j, 2])
        cv2.circle(im, (cx, cy), max(8, int(tr.target_px / 2)), (0, 255, 0), 3)
        cv2.drawMarker(im, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 22, 3)
        if abs(ft - seed_t) < 1.0:
            cv2.rectangle(im, (x, y), (x + w, y + h), (0, 0, 255), 3)
        cv2.putText(im, f"t={ft:.1f}", (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        tiles.append(im)
    sheet = np.hstack(tiles)
    sc = min(1.0, 1300.0 / sheet.shape[1])
    if sc < 1.0:
        sheet = cv2.resize(sheet, (int(sheet.shape[1] * sc), int(sheet.shape[0] * sc)))
    _save("tap.jpg", sheet)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 1
    if a[0] == "motion":
        cmd_motion(a[1], float(a[2]))
    elif a[0] == "scrub":
        cmd_scrub(a[1], [float(x) for x in a[2:]])
    elif a[0] == "zoom":
        cmd_zoom(a[1], float(a[2]), *map(int, a[3:7]))
    elif a[0] == "tap":
        cmd_tap(a[1], *map(int, a[2:6]), float(a[6]))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
