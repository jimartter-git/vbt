"""Plate geometry + camera angle → the px→m scale policy.

The scale reference is the **outer rim = the largest plate on the sleeve** (plates load
largest-first; the smaller 35/25/10/5 are concentric circles *inside* the big plate's
silhouette — the same inner circles a naive detector mistakes for the rim). So scale
needs the LARGEST plate's diameter, not the total load.

Diameter depends on kind: bumpers are ~constant (≈450 mm for ≥10 kg); iron shrinks with
the plate and is brand-dependent (lower confidence). Camera angle decides whether
plate-diameter scaling is even valid:
  - side      → plate is a clean circle; diameter valid; vertical motion true (best case)
  - diagonal  → plate is an ellipse (measure the MAJOR axis); motion has an out-of-plane
                arc → the trajectory needs the rim-anchor correction; reduced confidence
  - head-on   → plate is edge-on; diameter is unmeasurable → fall back to anthropometric
                scale (or report relative-only)
"""
from __future__ import annotations
from dataclasses import dataclass

LB_PER_KG = 2.2046226

# Standard OUTER diameters (metres) by the LARGEST plate on the sleeve.
# Bumpers: IWF/Olympic bumpers are 450 mm for every weight ≥10 kg (only sub-10 kg change
# plates are smaller — and those are essentially never the largest plate in a working set).
BUMPER_M = 0.450
# Iron/steel Olympic plates: APPROXIMATE (brand-dependent) — keyed by the plate's lb size.
IRON_DIAMETER_M = {45: 0.450, 35: 0.415, 25: 0.390, 10: 0.250, 5: 0.205, 2.5: 0.160}
IRON_DIAMETER_KG_M = {20: 0.450, 15: 0.400, 10: 0.350, 5: 0.230, 2.5: 0.190, 1.25: 0.160}

# Camera-angle → scale policy. `conf` multiplies the scale confidence; `needs_anchor`
# flags that the trajectory has an out-of-plane component (use FlowTracker anchor_alpha);
# `valid` is False when plate-diameter scaling can't work (head-on) → caller falls back.
ANGLE_POLICY = {
    "side":     {"valid": True,  "conf": 1.00, "needs_anchor": False, "axis": "diameter"},
    "diagonal": {"valid": True,  "conf": 0.70, "needs_anchor": True,  "axis": "major"},
    "front":    {"valid": False, "conf": 0.0,  "needs_anchor": False, "axis": None},
}


def _nearest(table: dict, key: float) -> float:
    return table[min(table, key=lambda k: abs(k - key))]


def plate_diameter_m(top_plate, kind: str = "bumper", unit: str = "lb") -> tuple[float, float]:
    """Outer-rim diameter (m) of the LARGEST plate, plus a 0..1 confidence.

    `top_plate`: the largest plate on the sleeve (e.g. 45 lb / 20 kg). For a stack, pass
    the biggest one — `largest_plate()` extracts it. `kind`: "bumper" | "iron".
    Bumpers are high-confidence (standardised); iron is approximate (brand-dependent)."""
    kind = kind.lower()
    if kind == "bumper":
        # ≥10 kg bumpers are all 450 mm; only tiny change plates differ.
        kg = (top_plate / LB_PER_KG) if unit == "lb" else top_plate
        return (BUMPER_M, 0.95) if kg >= 9.5 else (max(0.30, BUMPER_M * 0.6), 0.6)
    if kind == "iron":
        table = IRON_DIAMETER_M if unit == "lb" else IRON_DIAMETER_KG_M
        return (_nearest(table, top_plate), 0.7)        # approximate → lower confidence
    raise ValueError(f"unknown plate kind '{kind}'; use 'bumper' or 'iron'")


def largest_plate(plates):
    """The scale-determining plate from a stack (e.g. [45,35,25,10,5] → 45). The outer
    rim is the biggest plate; the rest are concentric circles inside it."""
    return max(plates) if plates else None


@dataclass
class ScaleSpec:
    """What the user knows (plate) + how it was filmed (angle) → a deterministic scale.

    `top_plate`/`kind`/`unit` fix the real-world diameter (handles stacking via the
    largest plate); `angle` fixes whether plate-diameter scaling is valid, how to measure
    the rim (circle vs ellipse major axis), whether the trajectory needs out-of-plane
    correction, and the confidence multiplier."""
    top_plate: float = 45.0
    kind: str = "bumper"
    unit: str = "lb"
    angle: str = "side"

    @property
    def policy(self) -> dict:
        if self.angle not in ANGLE_POLICY:
            raise ValueError(f"unknown angle '{self.angle}'; use {list(ANGLE_POLICY)}")
        return ANGLE_POLICY[self.angle]

    def plate_m(self) -> float:
        return plate_diameter_m(self.top_plate, self.kind, self.unit)[0]

    def scale_confidence(self) -> float:
        """Combined confidence: plate-size certainty × angle factor (0 when head-on)."""
        return plate_diameter_m(self.top_plate, self.kind, self.unit)[1] * self.policy["conf"]
