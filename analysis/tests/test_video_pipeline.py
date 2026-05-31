"""Synthetic-fixture tests for the video velocity pipeline.

We render a dark disc (a "plate") doing 3 clean reps of known vertical motion, then
assert the pipeline recovers the right per-rep velocity/ROM — through both the
in-memory path and a real H.264 mp4 encode→decode round-trip (the real-clip path).
"""
import os
import sys
import tempfile

import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vbt_video import (ArrayFrameSource, PyAVDecoder, VideoVelocitySource,
                       VideoConfig, PlateTracker, FlowTracker, auto_seed_bbox)  # noqa: E402

W, H, FPS, R = 240, 320, 60.0, 40           # frame + disc radius (px)
T, N_REPS, A = 2.0, 3, 0.25                  # rep period (s), reps, amplitude (m)
PLATE_M = 0.45
MPP = PLATE_M / (2 * R)                       # m per px implied by the disc size
EXP_MEAN = 4 * A / T                          # 0.5 m/s   (2A travel over T/2)
EXP_PEAK = A * 2 * np.pi / T                   # ~0.785 m/s
EXP_ROM_CM = 2 * A * 100                        # 50 cm


def _frames():
    cy0 = H / 2.0
    imgs = []
    for i in range(int(N_REPS * T * FPS)):
        t = i / FPS
        pos = -A * np.cos(2 * np.pi * t / T)   # up-positive m; starts at bottom, rest
        cy = int(round(cy0 - pos / MPP))       # image y grows down → up = smaller y
        im = np.full((H, W, 3), 230, np.uint8)
        cv2.circle(im, (W // 2, cy), R, (25, 25, 25), -1)
        imgs.append(im)
    return imgs


def _seed():
    pos0 = -A
    cy = int(round(H / 2.0 - pos0 / MPP))
    return (W // 2 - R, cy - R, 2 * R, 2 * R)


def _assert_reps(reps):
    assert abs(len(reps) - N_REPS) <= 1, f"expected ~{N_REPS} reps, got {len(reps)}"
    for r in reps:
        assert abs(r["mean_velocity"] - EXP_MEAN) < 0.08, r
        assert abs(r["peak_velocity"] - EXP_PEAK) < 0.12, r
        assert abs(r["rom"] - EXP_ROM_CM) < 8, r


def test_core_inmemory():
    # CSRT region tracker on a clean disc — validates the decode→scale→kinematics seams.
    reps, meta = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="csrt")).estimate(
        ArrayFrameSource(_frames(), FPS), seed_bbox=_seed())
    assert meta["track_confidence"] > 0.9
    assert abs(meta["m_per_px"] - MPP) / MPP < 0.1   # scaler within 10%
    _assert_reps(reps)


def test_auto_seed_finds_the_plate():
    box = auto_seed_bbox(_frames()[0])
    x, y, w, h = box
    # bbox center should be near the disc center, and size near the disc
    assert abs((x + w / 2) - W / 2) < 20
    assert 0.6 * (2 * R) < max(w, h) < 1.6 * (2 * R)


def _write_mp4(path, imgs, fps):
    import av
    c = av.open(path, "w")
    st = c.add_stream("libx264", rate=int(fps))
    st.width, st.height, st.pix_fmt = imgs[0].shape[1], imgs[0].shape[0], "yuv420p"
    for im in imgs:
        for pkt in st.encode(av.VideoFrame.from_ndarray(im, format="bgr24")):
            c.mux(pkt)
    for pkt in st.encode():
        c.mux(pkt)
    c.close()


def test_full_mp4_roundtrip():
    imgs = _frames()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "synthetic.mp4")
        _write_mp4(p, imgs, FPS)
        dec = PyAVDecoder(p)
        ts = [f.t for f in dec]
        assert len(ts) >= len(imgs) - 2                 # decoder returns the frames
        assert all(b > a for a, b in zip(ts, ts[1:]))   # timestamps increase
        reps, meta = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="csrt")).estimate(
            p, seed_bbox=_seed())
        _assert_reps(reps)


def _frames_with_distractor():
    """The moving plate PLUS a *stationary* same-size disc inside the search band — a
    background 'circle' a naive nearest-neighbour tracker would happily lock onto."""
    cy0 = H / 2.0
    dist_c = (160, 70)                                   # stationary distractor (in-band, out of the plate's path)
    imgs = []
    for i in range(int(N_REPS * T * FPS)):
        t = i / FPS
        pos = -A * np.cos(2 * np.pi * t / T)
        cy = int(round(cy0 - pos / MPP))
        im = np.full((H, W, 3), 230, np.uint8)
        cv2.circle(im, dist_c, R, (30, 30, 30), -1)     # distractor first (may be overdrawn)
        cv2.circle(im, (W // 2, cy), R, (25, 25, 25), -1)
        imgs.append(im)
    return imgs


def test_plate_tracker_rejects_stationary_distractor():
    # The min-acceleration DP must follow the *moving* plate, not the stationary disc —
    # motion-coherence is what appearance/intensity can't give us (both discs are gray).
    src = ArrayFrameSource(_frames_with_distractor(), FPS)

    # 1) the recovered trajectory stays on the plate's lane (x≈120), never the distractor (x=160)
    track = PlateTracker().track(src, _seed())
    assert abs(np.median(track.traj[:, 1]) - W // 2) < 20      # cx near the moving plate
    assert track.traj[:, 1].max() < 150                        # never jumps to the distractor lane

    # 2) and the per-rep velocity/ROM still come out right
    reps, _ = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="plate")).estimate(
        src, seed_bbox=_seed())
    assert abs(len(reps) - N_REPS) <= 1, f"expected ~{N_REPS} reps, got {len(reps)}"
    for r in reps:
        assert abs(r["mean_velocity"] - EXP_MEAN) < 0.12, r    # looser: Hough centre jitter
        assert abs(r["rom"] - EXP_ROM_CM) < 12, r


def _textured_frames():
    """A moving disc with fixed interior **texture** — optical flow needs feature points
    to track (a flat disc has none). The texture rides with the disc, so flow follows it."""
    rng = np.random.default_rng(0)
    texture = rng.integers(0, 255, (2 * R, 2 * R, 3), dtype=np.uint8)
    circ_mask = np.zeros((2 * R, 2 * R), np.uint8)
    cv2.circle(circ_mask, (R, R), R, 255, -1)
    cy0 = H / 2.0
    imgs = []
    for i in range(int(N_REPS * T * FPS)):
        t = i / FPS
        pos = -A * np.cos(2 * np.pi * t / T)
        cy = int(round(cy0 - pos / MPP))
        im = np.full((H, W, 3), 230, np.uint8)
        sub = im[cy - R:cy + R, W // 2 - R:W // 2 + R]
        sub[circ_mask > 0] = texture[circ_mask > 0]
        imgs.append(im)
    return imgs


def test_flow_tracker_holds_lock_through_the_set():
    # The optical-flow default: track texture frame-to-frame, hold lock the whole set
    # (high confidence), and recover the reps — the never-drops-a-rep behaviour.
    track = FlowTracker().track(ArrayFrameSource(_textured_frames(), FPS), _seed())
    assert track.confidence > 0.9                       # flow held lock across the set
    reps, meta = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="flow")).estimate(
        ArrayFrameSource(_textured_frames(), FPS), seed_bbox=_seed())
    _assert_reps(reps)
