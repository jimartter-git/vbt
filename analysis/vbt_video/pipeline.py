"""The video VelocitySource — ties the seams together.

`VideoVelocitySource.estimate(source_or_path, seed_bbox)` → (reps, meta), where
reps are the same shape every meVBT source emits. Output vendor id = `mevbt_cv`,
so it drops straight into the dataset next to the commercial tools and into fusion.
"""
from __future__ import annotations
from dataclasses import dataclass

from .frames import FrameSource, PyAVDecoder
from .track import (CSRTTracker, PlateTracker, FlowTracker, PoseTracker, Tracker,
                    auto_seed_bbox)
from .kinematics import PlateDiameterScaler, AnthropometricScaler, trajectory_to_reps


@dataclass
class VideoConfig:
    plate_m: float = 0.45        # known plate diameter (standard bumper)
    tracker: str = "flow"        # front-end selector (extend as trackers are added)
    peak_min: float = 0.12       # m/s noise gate (below grind speed — keep terminal reps)
    rom_min: float = 0.25        # m minimum real travel for a rep (absolute gate)
    rep_gate: str = "absolute"   # "absolute" (fixed gates) | "relative" (adaptive,
    #   tempo-invariant: gate each rep vs the set median, so fast TnG / partial-lockout
    #   reps aren't dropped — see kinematics._segment_concentric)
    band: tuple | None = None    # (x0,x1) px lane for the plate detector; None → seed-derived
    # --- px→m scale source (the Scaler seam, chosen independently of the Tracker) ---
    # "implement" → the tracker's own ruler (plate diameter for flow/plate/csrt; body
    #   segment for pose). "anthro" → a body segment measured by a *separate pose pass*,
    #   so we can track the plate for robust POSITION yet scale off the lifter — never
    #   trusting a plate diameter (fragile across rubber/iron/hex plates & camera angle).
    scale: str = "implement"     # "implement" | "anthro"
    # --- pose / equipment-free path (tracker="pose") AND the anthro scale source ---
    landmark: str = "wrist"      # body point to follow (wrist=cable/isolation, hip=bodyweight)
    side: str = "auto"           # "left" / "right" / "auto" (most-visible)
    height_m: float = 1.75       # user height → anthropometric px→m scale
    segment: str = "forearm"     # body segment used as the metric ruler
    # FlowTracker position anchor: 0 = off (flow owns position, the validated default);
    # >0 slowly pulls position to the plate's rim centre, correcting the smooth centroid
    # migration on row arcs (side 1.17→0.86 at 0.3; a no-op on square-on bench). Opt-in.
    flow_anchor_alpha: float = 0.0
    # FlowTracker occlusion handling: coast through short gaps + re-acquire via the plate
    # detector when the target leaves frame / is occluded. Off by default (validated path
    # unchanged); force-on for cluttered or edge-clipping clips.
    occlusion_robust: bool = False
    # Auto-fallback: if the default flow track comes back with LOW confidence (it lost lock),
    # transparently retry with occlusion_robust and keep the better track. No-op on healthy
    # clips (they never trip the threshold), so it can't regress the easy case — it only
    # rescues the hard one. Set occlusion_conf=0 to disable.
    auto_occlusion: bool = True
    occlusion_conf: float = 0.75


# Which two landmarks bound each scale segment (their pixel distance = the metric ruler).
_SEGMENT_LANDMARKS = {"forearm": ("wrist", "elbow"), "upper_arm": ("elbow", "shoulder")}

# Tracker factories receive the VideoConfig so a tracker can read its own knobs
# (e.g. the x-band, or the pose landmark/side) while trackers that don't need them ignore it.
_TRACKERS = {
    "csrt": lambda cfg: CSRTTracker(),
    "plate": lambda cfg: PlateTracker(band=cfg.band),
    "flow": lambda cfg: FlowTracker(band=cfg.band, anchor_alpha=cfg.flow_anchor_alpha,
                                    occlusion_robust=cfg.occlusion_robust),
    "pose": lambda cfg: PoseTracker(landmark=cfg.landmark, side=cfg.side,
                                    scale_segment=_SEGMENT_LANDMARKS.get(cfg.segment,
                                                                         ("wrist", "elbow"))),
}


class VideoVelocitySource:
    sourceID = "mevbt_cv"

    def __init__(self, config: VideoConfig | None = None):
        self.cfg = config or VideoConfig()
        # Injectable for tests: the landmark provider used by the *anthro scale* pose pass
        # (mirrors how PoseTracker's own provider is injected). None → real MediaPipe.
        self._scale_pose_provider = None

    def _tracker(self) -> Tracker:
        try:
            return _TRACKERS[self.cfg.tracker](self.cfg)
        except KeyError:
            raise ValueError(f"unknown tracker '{self.cfg.tracker}'; have {list(_TRACKERS)}")

    def _resolve_scale(self, src, track):
        """Return (m_per_px, scale_meta). The Scaler seam is chosen independently of the
        Tracker (positions and the metric ruler are separate concerns):

        - pose tracker → it already measured a body segment; scale anthropometrically.
        - `scale="anthro"` with an implement tracker → run a *separate* pose pass purely
          for the body-segment ruler, so plate/flow gives robust POSITION while px→m comes
          off the lifter (immune to plate type & angle). Falls back to the plate diameter
          if pose finds no segment (e.g. lifter out of frame).
        - otherwise → the plate diameter the tracker reported.
        """
        anthro = AnthropometricScaler(height_m=self.cfg.height_m, segment=self.cfg.segment)
        if self.cfg.tracker == "pose":
            return anthro.m_per_px(track.target_px), {"scale_source": "anthro"}
        if self.cfg.scale == "anthro":
            seg = _SEGMENT_LANDMARKS.get(self.cfg.segment, ("wrist", "elbow"))
            ptrack = PoseTracker(landmark=self.cfg.landmark, side=self.cfg.side,
                                 scale_segment=seg,
                                 provider=self._scale_pose_provider).track(src, None)
            if ptrack.target_px > 0:
                return anthro.m_per_px(ptrack.target_px), {
                    "scale_source": "anthro",
                    "scale_target_px": round(ptrack.target_px, 1),
                    "scale_confidence": ptrack.confidence,
                }
            # pose found no scale segment — degrade gracefully to the implement ruler
        return PlateDiameterScaler(self.cfg.plate_m).m_per_px(track.target_px), \
            {"scale_source": "implement"}

    def estimate(self, source_or_path, seed_bbox=None):
        """`source_or_path`: a FrameSource or a video path. `seed_bbox`: (x,y,w,h)
        around the target; if None, auto-seed from the first frame. The pose tracker
        ignores `seed_bbox` (it needs no seed) — leave it None there."""
        src = source_or_path if isinstance(source_or_path, FrameSource) else PyAVDecoder(source_or_path)
        if seed_bbox is None and self.cfg.tracker != "pose":
            seed_bbox = auto_seed_bbox(src.first().img)
        track = self._tracker().track(src, seed_bbox)
        # Auto-fallback: a low-confidence flow track means lost lock — retry occlusion-robust
        # and keep whichever held better. Healthy clips skip this entirely (no regression).
        used_occlusion = self.cfg.occlusion_robust
        if (self.cfg.auto_occlusion and self.cfg.tracker == "flow"
                and not self.cfg.occlusion_robust
                and track.confidence < self.cfg.occlusion_conf):
            alt = FlowTracker(band=self.cfg.band, anchor_alpha=self.cfg.flow_anchor_alpha,
                              occlusion_robust=True).track(src, seed_bbox)
            if alt.confidence > track.confidence:
                track, used_occlusion = alt, True
        mpp, scale_meta = self._resolve_scale(src, track)
        reps = trajectory_to_reps(track.traj, mpp, self.cfg.peak_min, self.cfg.rom_min,
                                  rep_gate=self.cfg.rep_gate)
        meta = {
            "m_per_px": mpp,
            "target_px": track.target_px,
            "track_confidence": track.confidence,
            "occlusion_used": used_occlusion,
            "n_frames": len(track.traj),
            "fps": round(src.fps, 2),
            "seed_bbox": tuple(int(v) for v in seed_bbox) if seed_bbox else None,
            **scale_meta,
        }
        return reps, meta
