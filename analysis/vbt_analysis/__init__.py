"""VBT offline analysis pipeline.

Rep detection + ZUPT-based velocity estimation for wrist-IMU recordings, plus
tooling to compare watch-derived velocity against Vitruve ground truth.

This is the PoC estimator. Once calibration confirms the signal, the core
algorithm (`velocity.py` / `rep_detect.py`) gets ported into the Swift
`VBTCore` package so the same logic runs on-device.
"""

from .ingest import load_session, synthetic_set
from .velocity import vertical_acceleration, integrate_with_zupt, rep_metrics
from .rep_detect import detect_turnarounds

__all__ = [
    "load_session",
    "synthetic_set",
    "vertical_acceleration",
    "integrate_with_zupt",
    "rep_metrics",
    "detect_turnarounds",
]
