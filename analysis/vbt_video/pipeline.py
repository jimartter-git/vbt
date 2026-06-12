"""The video VelocitySource — ties the seams together.

`VideoVelocitySource.estimate(source_or_path, seed_bbox)` → (reps, meta), where
reps are the same shape every meVBT source emits. Output vendor id = `mevbt_cv`,
so it drops straight into the dataset next to the commercial tools and into fusion.
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from .frames import FrameSource, PyAVDecoder
from .track import (CSRTTracker, PlateTracker, FlowTracker, PoseTracker, DetectTracker,
                    ColorPlateTracker, PLATE_COLORS, Tracker, auto_seed_bbox, auto_seed_motion,
                    seed_candidates, track_bidirectional)
from .kinematics import PlateDiameterScaler, AnthropometricScaler, trajectory_to_reps
from .plates import ScaleSpec


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
    # Seed-size-independent plate-size calibration (FlowTracker): a wide Hough scan tries to
    # re-anchor the px→m scale so a too-small/loose seed can't inflate velocity. EXPERIMENTAL,
    # default OFF: stress-tested across the corpus, no single circle-selection rule is robust
    # across plate-size × clutter (it either misses the under-sized squat or breaks the
    # device-grade bench/rows). The reliable path today is a well-sized seed; the durable fix
    # is a learned plate detector (cv-fusion.md roadmap #6). Opt in per clip if it helps.
    robust_scale: bool = False
    # Auto-fallback: if the default flow track comes back with LOW confidence (it lost lock),
    # transparently retry with occlusion_robust and keep the better track. No-op on healthy
    # clips (they never trip the threshold), so it can't regress the easy case — it only
    # rescues the hard one. Set occlusion_conf=0 to disable.
    auto_occlusion: bool = True
    occlusion_conf: float = 0.75
    # User-confirmed plate + camera angle (vbt_video.plates.ScaleSpec). When set it drives:
    #   real-world plate_m (largest plate + bumper/iron, handling stacking), scale confidence
    #   (plate certainty × angle factor), the head-on fallback (plate-diameter invalid → use
    #   anthro / relative-only), and the diagonal out-of-plane trajectory anchor. Pixel
    #   diameter still comes from the seed/detector (the user adjusts that surface in-app).
    scale_spec: ScaleSpec | None = None
    # Relative-ROM floor for segmentation: reject reps whose ROM is < this fraction of the
    # set median (kills high-frequency detection jitter). 0 = off (flow path unchanged);
    # the seed-free "detect" tracker defaults it to 0.5 (jittery per-frame detection).
    rom_floor_frac: float = 0.0
    # measure plate diameter as the ellipse MAJOR axis (fix diagonal-plate 2x velocity, roadmap #2)
    ellipse_scale: bool = False
    # Rep-plausibility (position-anchor) gate: reject candidate reps that don't start at
    # the set's own bottom band / end wildly above its top band — the rack-in / un-rack /
    # near-failure lockout-drift phantoms (the over-count that corrupts velocity-loss,
    # learning #14). Relative to the set's own median ROM (tempo/scale/lift-invariant).
    # Default OFF (validated paths byte-identical); the AUTO path enables it.
    plausibility_gate: bool = False
    # learned/profile tracker (tracker='profile'): the working bumper colour for this gym/session
    # ('blue'/'red'/'green'/'yellow' or an (hsv_lo,hsv_hi) tuple). Reliable colour detect+size.
    plate_color: object = None
    # ADVISORY per-lift ROM prior band (lo_cm, hi_cm) — from dataset/priors/{lift}_rom.csv
    # (derived from Vitruve GT rows, dataset/tools/derive_rom_priors.py). Reps outside the
    # band get `rom_outlier: True` + a meta count. FLAG ONLY, never gates counts or
    # velocity (learning #16: priors advise, measurements decide). A whole-set outlier
    # pattern is a SCALE-error tell (the uncorrected diagonal benches read ~60 cm vs the
    # 32–42 cm bench band).
    rom_prior_cm: tuple = None
    # HUMAN-CONFIRMED plate rim diameter (px) — the "plate confirm/adjust" surface
    # (learning #10; WL Analysis precedent in dataset/INGESTION.md). Overrides the
    # tracker's measured target size for the px→m RULER only; tracking is untouched.
    # The fix for hub-vs-rim mismeasure (diagonal bumpers read ~2× without it). A
    # per-clip human MEASUREMENT like the tap seed — never auto-fitted.
    rim_px: float = None


# Which two landmarks bound each scale segment (their pixel distance = the metric ruler).
_SEGMENT_LANDMARKS = {"forearm": ("wrist", "elbow"), "upper_arm": ("elbow", "shoulder")}

def _flow_anchor(cfg) -> float:
    """The FlowTracker rim-anchor gain (opt-in via `flow_anchor_alpha`). A diagonal
    scale_spec marks `needs_anchor` in meta as ADVISORY only — we do NOT auto-apply the
    gain. The right correction is clip-specific: the validated 0.3 helps the barbell-row
    arc (ROW-2 1.09→0.96) but SPLITS the deadlift 2 reps into 7 (front-quarter view). So
    surface the hint; let the app/user opt in per clip rather than gate on angle alone."""
    return cfg.flow_anchor_alpha


# Tracker factories receive the VideoConfig so a tracker can read its own knobs
# (e.g. the x-band, or the pose landmark/side) while trackers that don't need them ignore it.
_TRACKERS = {
    "csrt": lambda cfg: CSRTTracker(),
    "plate": lambda cfg: PlateTracker(band=cfg.band),
    "flow": lambda cfg: FlowTracker(band=cfg.band, anchor_alpha=_flow_anchor(cfg),
                                    occlusion_robust=cfg.occlusion_robust,
                                    robust_scale=cfg.robust_scale,
                                    ellipse_scale=cfg.ellipse_scale),
    "pose": lambda cfg: PoseTracker(landmark=cfg.landmark, side=cfg.side,
                                    scale_segment=_SEGMENT_LANDMARKS.get(cfg.segment,
                                                                         ("wrist", "elbow"))),
    # Seed-free track-by-detection — the no-tap auto path (texture-agnostic; 8.5→~2.5 err).
    "detect": lambda cfg: DetectTracker(),
    # Profile tracker — per-gym plate colour -> reliable detect+size (beats SB abs-velocity).
    "profile": lambda cfg: ColorPlateTracker(*(PLATE_COLORS[cfg.plate_color]
                                              if isinstance(cfg.plate_color, str) else cfg.plate_color)),
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
        spec = self.cfg.scale_spec
        # Head-on (plate edge-on) → plate-diameter scaling is invalid; prefer the anthro ruler.
        if self.cfg.scale == "anthro" or (spec is not None and not spec.policy["valid"]):
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
            # pose found no scale segment — degrade to the plate ruler (flagged below)
        # Plate-diameter scale: real-world diameter from the user's spec (largest plate +
        # bumper/iron) if given, else the configured default. Pixel diameter from the
        # tracker — or from the HUMAN-CONFIRMED rim (cfg.rim_px), which outranks any
        # measurement (the plate confirm/adjust surface, learning #10).
        plate_m = spec.plate_m() if spec is not None else self.cfg.plate_m
        meta = {"scale_source": "plate_spec" if spec is not None else "implement"}
        if spec is not None:
            meta["scale_confidence"] = round(spec.scale_confidence(), 3)
            meta["camera_angle"] = spec.angle
            meta["scale_valid"] = spec.policy["valid"]
        target_px = track.target_px
        if self.cfg.rim_px:
            target_px = float(self.cfg.rim_px)
            meta["scale_source"] = "rim_confirmed"
            meta["scale_confidence"] = max(meta.get("scale_confidence", 0.9), 0.9)
        return PlateDiameterScaler(plate_m).m_per_px(target_px), meta

    # Bar speeds above this (m/s, mean concentric) are physically implausible for a loaded
    # lift — a near-certain sign of an inflated px→m scale (wrong/clipped plate, low-res
    # Hough under-sizing the radius). A pose-free sanity prior; tune as the corpus grows.
    _MAX_PLAUSIBLE_MEAN_VEL = 1.6
    _SIZE_CV_SUSPECT = 0.18        # plate-radius jitter above which the scale is unreliable

    def _scale_confidence(self, track, reps, scale_meta):
        """(scale_confidence 0..1, scale_suspect bool). Two pose-free signals:
        plate-radius stability (a jittery ruler is a bad ruler) and bar-speed
        plausibility (a 2× scale error shows up as impossible velocities). When pose
        gives a second ruler, scale_meta carries its own confidence and we defer to it."""
        if scale_meta.get("scale_source") == "anthro":
            return float(scale_meta.get("scale_confidence", 1.0)), False
        # plate_spec carries plate-certainty × angle factor; plain implement starts at 1.0
        conf = float(scale_meta.get("scale_confidence", 1.0))
        cv = getattr(track, "size_cv", 0.0)
        # a jittery MEASURED radius doesn't taint a HUMAN-CONFIRMED ruler
        if cv > 0 and scale_meta.get("scale_source") != "rim_confirmed":
            conf = min(conf, max(0.0, 1.0 - cv / self._SIZE_CV_SUSPECT * 0.5))
        mvs = [r["mean_velocity"] for r in reps]
        implausible = bool(mvs) and float(np.median(mvs)) > self._MAX_PLAUSIBLE_MEAN_VEL
        if implausible:
            conf = min(conf, 0.3)
        # head-on with no anthro fallback → plate scale is invalid; don't report a real m/s
        invalid_angle = scale_meta.get("scale_valid", True) is False
        size_jitter = (cv > self._SIZE_CV_SUSPECT
                       and scale_meta.get("scale_source") != "rim_confirmed")
        suspect = implausible or size_jitter or invalid_angle
        return round(conf, 3), suspect

    def _estimate_auto(self, src):
        """The no-tap AUTO path: flow⊕detect fusion (beats SmartBarbell on the corpus,
        1.4 vs 2.5 mean rep-count err). FLOW-FIRST / detect-fallback — flow (smooth, single
        object, motion auto-seed) is the more reliable estimator when it holds lock; the
        seed-free DetectTracker covers the cases flow can't track (dark/low-texture iron
        plates → flow goes static). Both run the relative gate; the pick is recorded in
        meta['auto_pick']. Flow's complementary strength fixes detect's clean-clip over-count;
        detect's covers flow's dark-plate failure."""
        from dataclasses import replace
        import numpy as _np
        from .kinematics import apply_plausibility
        # NOTE: the plausibility gate is applied POST-selection (on the winning track
        # only), never inside the candidate runs — gating before selection changes the
        # candidates' counts/regularity and can flip the pick onto a decoy (BN-4 12→3).
        base = replace(self.cfg, rep_gate="relative", ellipse_scale=True)
        # PROFILE-FIRST when this gym's plate colour is known (reliable detect+size -> the
        # most accurate VELOCITY; beats SB absolute on coloured plates). Then flow, then detect.
        if self.cfg.plate_color is not None:
            p_reps, p_meta = VideoVelocitySource(replace(base, tracker="profile")).estimate(src)
            if p_meta.get("track_confidence", 0.0) >= 0.6 and len(p_reps) >= 3:
                p_meta["auto_pick"] = "profile"; p_meta["velocity_reliable"] = True
                return apply_plausibility(p_reps), p_meta

        def _regularity(reps):
            if len(reps) < 3:
                return 0.0
            t = _np.array([r.get("t", 0.0) for r in reps]); d = _np.diff(t); d = d[d > 0]
            return 1.0 / (1.0 + _np.std(d) / d.mean()) if (len(d) > 1 and d.mean() > 0) else 0.0

        # CANDIDATE-GENERATION + FLOW-VERIFICATION: the motion seeder proposes several plate
        # candidates (ellipse-sized); run flow on each and KEEP the one that holds lock with a
        # plausible rep count + regular cadence. This localises the plate in clutter (mirror/
        # hex/multiple plates) where a single auto-seed picks a decoy — and flow gives the
        # smooth trajectory for velocity. Score = confidence × cadence-regularity.
        best = None
        for seed in seed_candidates(src):
            fr, fm = VideoVelocitySource(replace(base, tracker="flow")).estimate(src, seed_bbox=seed)
            if fm.get("static_track_suspect", False) or not (3 <= len(fr) <= 18):
                continue
            score = fm.get("track_confidence", 0.0) * _regularity(fr)
            if best is None or score > best[0]:
                best = (score, fr, fm)
        if best is not None:
            _, f_reps, f_meta = best
            f_meta["auto_pick"] = "flow"
            f_meta["velocity_reliable"] = True
            return apply_plausibility(f_reps), f_meta
        # No candidate held lock (dark/low-texture iron, hex, etc.) -> DetectTracker for the
        # COUNT, abstaining on absolute velocity (jittery per-frame centres; honest-velocity rule).
        d_reps, d_meta = VideoVelocitySource(replace(base, tracker="detect")).estimate(src)
        d_meta["auto_pick"] = "detect"
        # NO plausibility gate on the detect fallback: its per-frame centres are jittery
        # (the very reason this path abstains on velocity), so position-anchor
        # plausibility has nothing trustworthy to anchor on.
        for r in d_reps:
            r["velocity_relative_only"] = True
        d_meta["velocity_reliable"] = False
        return d_reps, d_meta

    def estimate(self, source_or_path, seed_bbox=None, seed_time=None):
        """`source_or_path`: a FrameSource or a video path. `seed_bbox`: (x,y,w,h)
        around the target; if None, auto-seed from the first frame. The pose tracker
        ignores `seed_bbox` (it needs no seed) — leave it None there.
        `seed_time` (s): tap-on-ANY-frame — the bbox is placed at the frame nearest
        this time and the flow tracker runs BOTH directions from it (the human-grade
        tap: seed where the plate is clearest, not wherever frame 0 happens to be)."""
        src = source_or_path if isinstance(source_or_path, FrameSource) else PyAVDecoder(source_or_path)
        if self.cfg.tracker == "auto":
            return self._estimate_auto(src)
        if seed_bbox is None and self.cfg.tracker not in ("pose", "detect", "profile"):
            # Zero-tap auto-seed: prefer the MOTION seeder (the circle that travels), which
            # avoids locking onto a static rack/background plate; fall back to the static
            # largest-blob seeder only if no moving circle is found. (cv-fusion roadmap #6.)
            seed_bbox = auto_seed_motion(src) or auto_seed_bbox(src.first().img)
        if seed_time is not None and self.cfg.tracker == "flow":
            # Bidirectional tap: the auto-occlusion retry doesn't apply (each leg already
            # starts at the best-visibility frame the user chose).
            track = track_bidirectional(
                src, seed_bbox, seed_time,
                lambda: FlowTracker(band=self.cfg.band, anchor_alpha=_flow_anchor(self.cfg),
                                    occlusion_robust=self.cfg.occlusion_robust,
                                    robust_scale=self.cfg.robust_scale,
                                    ellipse_scale=self.cfg.ellipse_scale))
            used_occlusion = self.cfg.occlusion_robust
        else:
            track = self._tracker().track(src, seed_bbox)
            # Auto-fallback: a low-confidence flow track means lost lock — retry occlusion-robust
            # and keep whichever held better. Healthy clips skip this entirely (no regression).
            used_occlusion = self.cfg.occlusion_robust
            if (self.cfg.auto_occlusion and self.cfg.tracker == "flow"
                    and not self.cfg.occlusion_robust
                    and track.confidence < self.cfg.occlusion_conf):
                alt = FlowTracker(band=self.cfg.band, anchor_alpha=self.cfg.flow_anchor_alpha,
                                  occlusion_robust=True, robust_scale=self.cfg.robust_scale
                                  ).track(src, seed_bbox)
                if alt.confidence > track.confidence:
                    track, used_occlusion = alt, True
        mpp, scale_meta = self._resolve_scale(src, track)
        # the seed-free detect tracker has jittery per-frame centres -> default a ROM floor
        rom_floor = self.cfg.rom_floor_frac or (0.5 if self.cfg.tracker == "detect" else 0.0)
        reps = trajectory_to_reps(track.traj, mpp, self.cfg.peak_min, self.cfg.rom_min,
                                  rom_floor_frac=rom_floor,
                                  rep_gate=self.cfg.rep_gate,
                                  plausibility=self.cfg.plausibility_gate)
        scale_conf, scale_suspect = self._scale_confidence(track, reps, scale_meta)
        if scale_suspect:
            # Honest-velocity rule (CLAUDE.md / docs): when the px→m ruler can't be
            # trusted, don't report a confident absolute m/s — mark reps relative-only.
            for r in reps:
                r["velocity_relative_only"] = True
        # Self-guard against a MIS-SEED. A track that barely moves vertically yet reports
        # HIGH confidence is almost always the seed sitting on a STATIC object (a rack-stored
        # plate, a background circle) — NOT a "CV failure". For any real lift the bar travels
        # well over a plate diameter, so a vertical span under ~0.3× the target size with
        # healthy confidence (and few/no reps) means: re-seed onto the WORKING (moving) plate
        # and re-run. (The 2026-06-05 bench lesson made programmatic — see
        # analysis/CV_ONBOARDING.md.)
        n_rom_outliers = 0
        if self.cfg.rom_prior_cm and reps:
            lo, hi = self.cfg.rom_prior_cm
            for r in reps:
                if not (lo <= r["rom"] <= hi):
                    r["rom_outlier"] = True          # advisory only — never gates
                    n_rom_outliers += 1
        y_span_px = float(np.ptp(track.traj[:, 2])) if len(track.traj) else 0.0
        static_track_suspect = bool(track.confidence >= 0.75 and track.target_px > 0
                                    and y_span_px < 0.30 * track.target_px)
        meta = {
            "m_per_px": mpp,
            "target_px": track.target_px,
            "track_confidence": track.confidence,
            "occlusion_used": used_occlusion,
            "scale_confidence": scale_conf,
            "scale_suspect": scale_suspect,
            "y_span_px": round(y_span_px, 1),
            "static_track_suspect": static_track_suspect,
            "n_frames": len(track.traj),
            "fps": round(src.fps, 2),
            "seed_bbox": tuple(int(v) for v in seed_bbox) if seed_bbox else None,
            "seed_time": (round(float(seed_time), 3) if seed_time is not None else None),
            "rom_prior_outliers": n_rom_outliers,
            **scale_meta,
        }
        return reps, meta
