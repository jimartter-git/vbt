"""meVBT video velocity pipeline.

Purely-video rep velocity, built to be *better and more flexible* than the
plate-circle-detection competitors — and architected so the tracking front-end is
swappable without redesigning anything downstream.

    FrameSource  →  Tracker  →  Scaler  →  Kinematics+Segmentation  →  reps
    (decode)       (pixels)     (px→m)     (shared with the rest of meVBT)

Why these seams matter (the anti-redesign guarantee):
- **FrameSource** (PyAV) gives frame-accurate, variable-frame-rate-safe timestamps
  — phones record VFR; deriving velocity needs real time, not assumed fps.
- **Tracker** is an interface. v1 = OpenCV CSRT region tracking (handles non-round
  plates / off-angle — the differentiator). Drop in pose/joint tracking,
  learned point-tracking (CoTracker), or segmentation (SAM) later with no change
  to scaling/kinematics.
- **Scaler** is an interface (px→m). v1 = known plate diameter; bar-length or a
  reference object slot in later.
- Output is the same `(rep boundaries, velocity, ROM, confidence)` contract as the
  watch/BLE sources → flows straight into fusion and the dataset (vendor=mevbt_cv).
"""
from .frames import Frame, FrameSource, ArrayFrameSource, PyAVDecoder
from .track import Tracker, CSRTTracker, auto_seed_bbox
from .kinematics import PlateDiameterScaler, trajectory_to_reps
from .pipeline import VideoConfig, VideoVelocitySource

__all__ = [
    "Frame", "FrameSource", "ArrayFrameSource", "PyAVDecoder",
    "Tracker", "CSRTTracker", "auto_seed_bbox",
    "PlateDiameterScaler", "trajectory_to_reps",
    "VideoConfig", "VideoVelocitySource",
]
