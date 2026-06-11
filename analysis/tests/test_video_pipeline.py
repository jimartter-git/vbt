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
                       VideoConfig, PlateTracker, FlowTracker, PoseTracker,
                       auto_seed_bbox)  # noqa: E402

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


def _occluded_textured_frames(occ):
    """The textured rep disc, but BLANKED (background only) on frame indices in `occ` —
    the plate leaves frame / is blocked for a beat while still 'moving' behind the gap,
    then reappears at its true (moved) position. Exercises coast + re-acquire."""
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
        if i not in occ:                                 # disc hidden during the gap
            sub = im[cy - R:cy + R, W // 2 - R:W // 2 + R]
            sub[circ_mask > 0] = texture[circ_mask > 0]
        imgs.append(im)
    return imgs


def test_occlusion_robust_recovers_after_target_leaves_frame():
    # The plate is occluded for ~0.4 s mid-set. Default flow freezes on the stale point
    # cloud and can't re-lock when it reappears at a new position; occlusion_robust
    # re-acquires via the detector and recovers the full rep count.
    occ = set(range(130, 155))                           # ~0.4 s blackout mid rep-2
    frames = _occluded_textured_frames(occ)
    plain = FlowTracker(occlusion_robust=False).track(ArrayFrameSource(frames, FPS), _seed())
    robust = FlowTracker(occlusion_robust=True).track(ArrayFrameSource(frames, FPS), _seed())
    assert robust.confidence >= plain.confidence          # re-acquire restores lock

    reps_plain, _ = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="flow")).estimate(
        ArrayFrameSource(frames, FPS), seed_bbox=_seed())
    reps_robust, _ = VideoVelocitySource(
        VideoConfig(plate_m=PLATE_M, tracker="flow", occlusion_robust=True)).estimate(
        ArrayFrameSource(frames, FPS), seed_bbox=_seed())
    assert len(reps_robust) >= len(reps_plain)            # never worse
    assert abs(len(reps_robust) - N_REPS) <= 1            # and recovers ~all reps


def test_auto_fallback_engages_occlusion_only_when_lock_is_poor():
    # The pipeline retries occlusion-robust when the default flow track is low-confidence,
    # and keeps it only if it tracks better. occlusion_conf=1.0 forces the retry to be
    # considered; auto_occlusion=False disables the whole policy.
    frames = _occluded_textured_frames(set(range(130, 155)))
    auto = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="flow",
                                           occlusion_conf=1.0))
    off = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="flow",
                                          auto_occlusion=False))
    _, m_auto = auto.estimate(ArrayFrameSource(frames, FPS), seed_bbox=_seed())
    _, m_off = off.estimate(ArrayFrameSource(frames, FPS), seed_bbox=_seed())
    assert m_auto["occlusion_used"] is True       # retried and kept the better (robust) track
    assert m_off["occlusion_used"] is False        # policy disabled → default track only


def test_scale_confidence_flags_implausible_velocity():
    # A clean disc with a CORRECT plate-diameter scale yields plausible velocities → the
    # scale is trusted (not suspect). But a grossly over-sized plate_m (here 5× too big)
    # inflates px→m and velocity ~5× → the bar-speed plausibility prior flags it, and the
    # reps are marked relative-only rather than reporting a confident wrong m/s.
    src = lambda: ArrayFrameSource(_frames(), FPS)
    _, m_ok = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="csrt")).estimate(
        src(), seed_bbox=_seed())
    assert m_ok["scale_suspect"] is False
    assert m_ok["scale_confidence"] > 0.5

    reps_bad, m_bad = VideoVelocitySource(
        VideoConfig(plate_m=PLATE_M * 5.0, tracker="csrt")).estimate(src(), seed_bbox=_seed())
    assert m_bad["scale_suspect"] is True
    assert all(r.get("velocity_relative_only") for r in reps_bad)


def test_flow_tracker_survives_a_featureless_seed():
    # A seed on a blank region finds no corner features. The tracker must NOT crash
    # (calcOpticalFlowPyrLK on an empty cloud used to assert-fail) — it should return a
    # low-confidence track gracefully.
    blank = [np.full((H, W, 3), 230, np.uint8) for _ in range(30)]
    track = FlowTracker().track(ArrayFrameSource(blank, FPS), (10, 10, 20, 20))
    assert track.traj.shape[0] == 30
    assert track.confidence < 0.5                         # nothing to track → honest low conf


def test_plate_spec_scale_and_angle_policy():
    from vbt_video.plates import plate_diameter_m, largest_plate, ScaleSpec
    # stacking: the outer rim = the largest plate
    assert largest_plate([45, 35, 25, 10, 5]) == 45
    # bumper ≥10 kg is ~450 mm and high-confidence; iron is approximate (lower conf)
    assert plate_diameter_m(45, "bumper") == (0.450, 0.95)
    d_iron, c_iron = plate_diameter_m(25, "iron")
    assert d_iron < 0.450 and c_iron < 0.95          # smaller iron plate, less certain
    assert plate_diameter_m(20, "bumper", unit="kg")[0] == 0.450
    # angle policy: side fully valid, diagonal needs the out-of-plane correction, head-on invalid
    assert ScaleSpec(angle="side").policy["valid"] is True
    assert ScaleSpec(angle="diagonal").policy["needs_anchor"] is True
    assert ScaleSpec(angle="front").policy["valid"] is False
    # combined confidence = plate certainty × angle factor (0 head-on, reduced diagonal)
    assert ScaleSpec(angle="side").scale_confidence() == 0.95
    assert ScaleSpec(angle="diagonal").scale_confidence() < 0.95
    assert ScaleSpec(angle="front").scale_confidence() == 0.0


def test_scale_spec_drives_plate_m_and_angle_flagging():
    from vbt_video.plates import ScaleSpec
    src = lambda: ArrayFrameSource(_frames(), FPS)
    # SIDE view, 45 lb bumper → plate_m 0.45 (== the fixture's implied scale), trusted, not suspect
    cfg = VideoConfig(tracker="csrt", scale_spec=ScaleSpec(top_plate=45, kind="bumper", angle="side"))
    reps, m = VideoVelocitySource(cfg).estimate(src(), seed_bbox=_seed())
    assert m["scale_source"] == "plate_spec"
    assert m["camera_angle"] == "side"
    assert abs(m["m_per_px"] - MPP) / MPP < 0.1
    assert m["scale_suspect"] is False
    _assert_reps(reps)
    # HEAD-ON: plate edge-on → plate-diameter invalid; with no pose segment it degrades to the
    # plate ruler but is FLAGGED (don't report a confident absolute m/s).
    s2 = VideoVelocitySource(VideoConfig(tracker="csrt", scale_spec=ScaleSpec(angle="front")))
    s2._scale_pose_provider = lambda img: {}        # pose finds no segment → fall through, flagged
    reps2, m2 = s2.estimate(src(), seed_bbox=_seed())
    assert m2["scale_suspect"] is True
    assert all(r.get("velocity_relative_only") for r in reps2)


def test_flow_tracker_holds_lock_through_the_set():
    # The optical-flow default: track texture frame-to-frame, hold lock the whole set
    # (high confidence), and recover the reps — the never-drops-a-rep behaviour.
    track = FlowTracker().track(ArrayFrameSource(_textured_frames(), FPS), _seed())
    assert track.confidence > 0.9                       # flow held lock across the set
    reps, meta = VideoVelocitySource(VideoConfig(plate_m=PLATE_M, tracker="flow")).estimate(
        ArrayFrameSource(_textured_frames(), FPS), seed_bbox=_seed())
    _assert_reps(reps)


# ---- Pose front-end (equipment-free path) ----
# We validate the pose seam WITHOUT the heavy MediaPipe model by injecting a synthetic
# landmark provider: a wrist doing 3 known "pushdown" reps, with a fixed forearm length.
# This exercises PoseTracker → AnthropometricScaler → kinematics exactly as a real clip would.

HEIGHT_M = 1.80
FOREARM_FRAC = 0.146
FOREARM_PX = 120.0                                   # forearm pixel length we emit
POSE_MPP = (HEIGHT_M * FOREARM_FRAC) / FOREARM_PX    # m per px the scaler should recover
P_EXP_MEAN = 4 * A / T                               # same 0.5 m/s motion as the disc fixtures
P_EXP_ROM_CM = 2 * A * 100                            # 50 cm


class _SyntheticPoseProvider:
    """A wrist landmark (right side) tracing the cos() rep motion, plus an elbow held a
    fixed forearm-length below it so the anthropometric scale is exact and known.
    `drop` frames return {} (no detection) to exercise the gap-fill + confidence path."""
    def __init__(self, drop=frozenset()):
        self.i = -1
        self.drop = drop

    def __call__(self, img):
        self.i += 1
        if self.i in self.drop:
            return {}
        t = self.i / FPS
        pos = -A * np.cos(2 * np.pi * t / T)         # up-positive metres
        wy = H / 2.0 - pos / POSE_MPP                 # image y grows down
        wx = W / 2.0
        return {
            "right_wrist": (wx, wy, 0.95),
            "right_elbow": (wx, wy + FOREARM_PX, 0.95),   # forearm = fixed px ruler
        }


def _pose_frames(n):
    # PoseTracker only times frames + calls the provider on each img; content is irrelevant.
    return ArrayFrameSource([np.zeros((H, W, 3), np.uint8) for _ in range(n)], FPS)


def test_pose_tracker_recovers_reps_via_anthropometric_scale():
    n = int(N_REPS * T * FPS)
    tracker = PoseTracker(landmark="wrist", side="auto",
                          provider=_SyntheticPoseProvider())
    track = tracker.track(_pose_frames(n), seed_bbox=None)   # pose needs no seed
    assert track.confidence > 0.95
    assert abs(track.target_px - FOREARM_PX) < 1.0           # forearm ruler recovered

    cfg = VideoConfig(tracker="pose", height_m=HEIGHT_M, segment="forearm")
    src = VideoVelocitySource(cfg)
    # inject the synthetic provider into the configured PoseTracker
    src._tracker = lambda: PoseTracker(landmark="wrist", side="auto",
                                       provider=_SyntheticPoseProvider())
    reps, meta = src.estimate(_pose_frames(n), seed_bbox=None)
    assert meta["seed_bbox"] is None                         # confirms the seed-free path
    assert abs(meta["m_per_px"] - POSE_MPP) / POSE_MPP < 0.02
    assert abs(len(reps) - N_REPS) <= 1, f"expected ~{N_REPS} reps, got {len(reps)}"
    for r in reps:
        assert abs(r["mean_velocity"] - P_EXP_MEAN) < 0.08, r
        assert abs(r["rom"] - P_EXP_ROM_CM) < 8, r


def test_pose_tracker_gap_fill_and_confidence():
    # Dropped detections are gap-filled (held last) and reflected in a lower confidence.
    n = int(N_REPS * T * FPS)
    drop = frozenset(range(40, 50))
    track = PoseTracker(provider=_SyntheticPoseProvider(drop=drop)).track(
        _pose_frames(n), seed_bbox=None)
    assert track.confidence < 1.0                            # the drop is reflected
    assert not np.isnan(track.traj[:, 2]).any()              # but the series is still clean


class _FixedForearmProvider:
    """Emits a wrist+elbow a FIXED pixel distance apart (the metric ruler) — content of
    the frame is irrelevant. Used to drive the *anthro scale* seam independently of the
    position tracker. Wrist position is static (only the segment LENGTH feeds the scaler)."""
    def __init__(self, forearm_px):
        self.forearm_px = forearm_px

    def __call__(self, img):
        return {"right_wrist": (W / 2.0, H / 2.0, 0.95),
                "right_elbow": (W / 2.0, H / 2.0 + self.forearm_px, 0.95)}


def _mixed_rom_traj(specs, fps=60.0, mpp=0.005):
    """Build a synthetic (t, cx, cy) trajectory from per-rep (amplitude_m, period_s)
    specs — one concentric (up) per period. Lets us test segmentation directly,
    no rendering. `mpp` is the px→m the caller passes to trajectory_to_reps."""
    ts, cys, cur = [], [], 0.0
    for A, T in specs:
        nf = int(T * fps)
        for i in range(nf):
            tt = i / fps
            pos = -A * np.cos(2 * np.pi * tt / T)        # 0 at bottom → up → bottom
            ts.append(cur + tt)
            cys.append(H / 2.0 - pos / mpp)              # image y grows down → up = smaller y
        cur += nf / fps
    return np.column_stack([ts, np.full(len(ts), W / 2.0), cys]), mpp


def test_relative_gate_recovers_partial_reps_that_absolute_drops():
    # 3 full slow reps (ROM 0.5 m) + 2 fast partial reps (ROM 0.2 m < absolute rom_min,
    # but normal peak velocity — the touch-and-go case). Absolute gating drops the
    # partials; peak-relative gating keeps all 5 and flags the partials as partial_rom.
    from vbt_video.kinematics import trajectory_to_reps
    traj, mpp = _mixed_rom_traj([(0.25, 2.0)] * 3 + [(0.10, 1.0)] * 2)

    reps_abs = trajectory_to_reps(traj, mpp, rep_gate="absolute")
    reps_rel = trajectory_to_reps(traj, mpp, rep_gate="relative")

    assert len(reps_abs) <= 3 + 1                         # absolute keeps ~the 3 full reps
    assert len(reps_rel) >= len(reps_abs) + 1             # relative recovers the partials
    assert abs(len(reps_rel) - 5) <= 1                    # ~all 5 reps
    partials = [r for r in reps_rel if r.get("flag") == "partial_rom"]
    assert len(partials) >= 2                             # the 2 short reps are flagged
    assert all(p["rom"] < 35 for p in partials)           # flagged reps are the short ones


def test_relative_gate_does_not_invent_reps_from_jitter():
    # A clean 3-rep set must still read as ~3 under relative gating — the peak-relative
    # rule rejects sub-threshold chatter rather than inflating the count.
    from vbt_video.kinematics import trajectory_to_reps
    traj, mpp = _mixed_rom_traj([(0.25, 2.0)] * 3)
    reps_rel = trajectory_to_reps(traj, mpp, rep_gate="relative")
    assert abs(len(reps_rel) - 3) <= 1


def _traj_with_rack_tail(n_reps=4, A=0.25, T=2.0, drift_m=0.15, lift_m=0.6,
                         fps=60.0, mpp=0.005):
    """`n_reps` clean reps, then the near-failure ENDGAME (the 20260609 BN-2/BN-4
    phantom source): from lockout (top), a slow drift UP into the hooks, then a big
    fast rack LIFT — two positive-velocity runs that START at the top, not the set's
    bottom anchor. Returns (traj, mpp)."""
    ts, cys = [], []
    cur = 0.0
    for _ in range(n_reps):
        nf = int(T * fps)
        for i in range(nf):
            tt = i / fps
            pos = -A * np.cos(2 * np.pi * tt / T)
            ts.append(cur + tt)
            cys.append(H / 2.0 - pos / mpp)
        cur += nf / fps
    # hold at the bottom a beat, rise to lockout (the last rep's top), pause...
    def _move(p0, p1, dur):
        nonlocal cur
        nf = max(2, int(dur * fps))
        for i in range(nf):
            a = i / (nf - 1)
            ts.append(cur + i / fps)
            cys.append(H / 2.0 - (p0 + a * (p1 - p0)) / mpp)
        cur += nf / fps
    _move(-A, A, T / 2)              # final ascent to lockout
    _move(A, A, 0.8)                 # hold at lockout
    _move(A, A + drift_m, 0.7)       # slow drift UP toward the hooks (phantom 1)
    _move(A + drift_m, A + drift_m, 0.5)
    _move(A + drift_m, A + drift_m + lift_m, 0.5)   # fast rack lift (phantom 2)
    return np.column_stack([np.asarray(ts), np.full(len(ts), W / 2.0),
                            np.asarray(cys)]), mpp


def test_plausibility_gate_drops_rack_phantoms():
    # Without the gate the lockout-drift + rack-lift runs read as extra "reps" (the
    # near-failure over-count that also corrupts velocity-loss — learning #14). The
    # position-anchor gate drops them: they start at the TOP, not the set's bottom band.
    from vbt_video.kinematics import trajectory_to_reps
    traj, mpp = _traj_with_rack_tail(n_reps=4)
    n_real = 4 + 1                                       # 4 cycles + the final ascent
    off = trajectory_to_reps(traj, mpp, rep_gate="relative")
    on = trajectory_to_reps(traj, mpp, rep_gate="relative", plausibility=True)
    assert len(off) > n_real                             # phantoms got counted before
    assert len(on) == n_real                             # gate drops exactly the phantoms
    # and the surviving reps are the REAL ones (start at the bottom anchor)
    starts = [r["pos_start"] for r in on]
    assert max(starts) - min(starts) < 0.2 * 2 * 0.25 / 1  # tight bottom band (m)


def test_plausibility_gate_keeps_partial_reps():
    # Partial (short-lockout) reps end BELOW the top band — the gate is one-sided and
    # must keep them (the SQ-3 touch-and-go lesson: count, flag, don't drop).
    from vbt_video.kinematics import trajectory_to_reps
    traj, mpp = _mixed_rom_traj([(0.25, 2.0)] * 3 + [(0.10, 1.0)] * 2)
    on = trajectory_to_reps(traj, mpp, rep_gate="relative", plausibility=True)
    off = trajectory_to_reps(traj, mpp, rep_gate="relative")
    assert len(on) == len(off)                           # gate is a no-op here
    assert sum(1 for r in on if r.get("flag") == "partial_rom") >= 2


def test_plausibility_gate_noop_on_clean_set():
    from vbt_video.kinematics import trajectory_to_reps
    traj, mpp = _mixed_rom_traj([(0.25, 2.0)] * 5)
    on = trajectory_to_reps(traj, mpp, rep_gate="relative", plausibility=True)
    off = trajectory_to_reps(traj, mpp, rep_gate="relative")
    assert [r["t"] for r in on] == [r["t"] for r in off]  # identical reps


def test_plausibility_gate_is_trailing_only():
    # A LEADING positional outlier (e.g. real reps measured with distorted geometry at
    # the start — the dead-front ROW-4 case, or a clip that opens mid-rep) is never
    # stripped: the validated phantom family (rack-in / put-down / lockout drift) is
    # TERMINAL by mechanism, and judging early reps positionally mis-fires.
    from vbt_video.kinematics import apply_plausibility
    reps = [dict(rep_index=i + 1, t=float(i), t_end=i + 0.8, mean_velocity=0.5,
                 peak_velocity=0.8, rom=50.0, pos_start=0.0, pos_end=0.5)
            for i in range(6)]
    reps[0]["pos_start"] = 0.6                      # leading outlier (>0.5×ROM off)
    reps[0]["pos_end"] = 1.1
    assert len(apply_plausibility(reps)) == 6       # kept — gate only strips the tail


def test_plausibility_gate_abstains_on_incoherent_positions():
    # When start positions are all over the place relative to ROM (a jittery /
    # resonating track — dark-iron rows), set statistics mean nothing: the gate
    # must abstain entirely rather than strip real reps.
    import numpy as np
    from vbt_video.kinematics import apply_plausibility
    rng = np.random.default_rng(1)
    reps = []
    for i in range(10):
        s = float(rng.uniform(-0.5, 0.5))           # MAD(start) >> 0.25 × ROM (0.1 m)
        reps.append(dict(rep_index=i + 1, t=float(i), t_end=i + 0.8, mean_velocity=0.5,
                         peak_velocity=0.8, rom=10.0, pos_start=s, pos_end=s + 0.1))
    assert len(apply_plausibility(reps)) == 10      # abstained — nothing stripped


def test_hybrid_anthro_scale_with_implement_position_tracker():
    # The Scaler seam is independent of the Tracker: track the disc for POSITION (CSRT),
    # but take px→m from a body segment (a separate pose pass) — the plate-type/angle-robust
    # path. Size the synthetic forearm so the anthro scale equals the disc's implied MPP,
    # then the hybrid must recover the same reps as the implement-scaled pipeline.
    forearm_px = (1.80 * FOREARM_FRAC) / MPP          # → AnthropometricScaler gives MPP
    cfg = VideoConfig(plate_m=PLATE_M, tracker="csrt", scale="anthro",
                      height_m=1.80, segment="forearm")
    src = VideoVelocitySource(cfg)
    src._scale_pose_provider = _FixedForearmProvider(forearm_px)   # inject the ruler
    reps, meta = src.estimate(ArrayFrameSource(_frames(), FPS), seed_bbox=_seed())
    assert meta["scale_source"] == "anthro"
    assert abs(meta["m_per_px"] - MPP) / MPP < 0.02                # scale came off the segment
    _assert_reps(reps)                                             # same reps as implement scale


def test_hybrid_falls_back_to_implement_when_pose_finds_no_segment():
    # If the lifter (scale segment) isn't visible, anthro scale degrades gracefully to the
    # plate-diameter ruler rather than producing garbage.
    cfg = VideoConfig(plate_m=PLATE_M, tracker="csrt", scale="anthro")
    src = VideoVelocitySource(cfg)
    src._scale_pose_provider = lambda img: {}                      # never finds a segment
    reps, meta = src.estimate(ArrayFrameSource(_frames(), FPS), seed_bbox=_seed())
    assert meta["scale_source"] == "implement"                     # fell back to the plate
    _assert_reps(reps)
