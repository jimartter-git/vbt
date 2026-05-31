"""The video VelocitySource — ties the seams together.

`VideoVelocitySource.estimate(source_or_path, seed_bbox)` → (reps, meta), where
reps are the same shape every meVBT source emits. Output vendor id = `mevbt_cv`,
so it drops straight into the dataset next to the commercial tools and into fusion.
"""
from __future__ import annotations
from dataclasses import dataclass

from .frames import FrameSource, PyAVDecoder
from .track import CSRTTracker, PlateTracker, FlowTracker, Tracker, auto_seed_bbox
from .kinematics import PlateDiameterScaler, trajectory_to_reps


@dataclass
class VideoConfig:
    plate_m: float = 0.45        # known plate diameter (standard bumper)
    tracker: str = "flow"        # front-end selector (extend as trackers are added)
    peak_min: float = 0.12       # m/s noise gate (below grind speed — keep terminal reps)
    rom_min: float = 0.25        # m minimum real travel for a rep
    band: tuple | None = None    # (x0,x1) px lane for the plate detector; None → seed-derived


# Tracker factories receive the VideoConfig so a tracker can read its own knobs
# (e.g. the x-band) while a tracker that doesn't need them (csrt) just ignores it.
_TRACKERS = {
    "csrt": lambda cfg: CSRTTracker(),
    "plate": lambda cfg: PlateTracker(band=cfg.band),
    "flow": lambda cfg: FlowTracker(band=cfg.band),
}


class VideoVelocitySource:
    sourceID = "mevbt_cv"

    def __init__(self, config: VideoConfig | None = None):
        self.cfg = config or VideoConfig()

    def _tracker(self) -> Tracker:
        try:
            return _TRACKERS[self.cfg.tracker](self.cfg)
        except KeyError:
            raise ValueError(f"unknown tracker '{self.cfg.tracker}'; have {list(_TRACKERS)}")

    def estimate(self, source_or_path, seed_bbox=None):
        """`source_or_path`: a FrameSource or a video path. `seed_bbox`: (x,y,w,h)
        around the target; if None, auto-seed from the first frame."""
        src = source_or_path if isinstance(source_or_path, FrameSource) else PyAVDecoder(source_or_path)
        if seed_bbox is None:
            seed_bbox = auto_seed_bbox(src.first().img)
        track = self._tracker().track(src, seed_bbox)
        mpp = PlateDiameterScaler(self.cfg.plate_m).m_per_px(track.target_px)
        reps = trajectory_to_reps(track.traj, mpp, self.cfg.peak_min, self.cfg.rom_min)
        meta = {
            "m_per_px": mpp,
            "target_px": track.target_px,
            "track_confidence": track.confidence,
            "n_frames": len(track.traj),
            "fps": round(src.fps, 2),
            "seed_bbox": tuple(int(v) for v in seed_bbox),
        }
        return reps, meta
