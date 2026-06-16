"""Frame sources — the decode seam.

A `FrameSource` yields `Frame(t_seconds, bgr_image)` and is **re-iterable** (each
`iter()` is a fresh pass). PyAV is the production decoder: real PTS timestamps,
variable-frame-rate-safe. ArrayFrameSource backs synthetic tests with no file I/O.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, List

import numpy as np


@dataclass
class Frame:
    t: float            # seconds (real timestamp; None-safe filled by sources)
    img: np.ndarray     # H x W x 3, BGR, uint8


class FrameSource(ABC):
    """Re-iterable source of timestamped frames."""
    @property
    @abstractmethod
    def fps(self) -> float: ...

    @abstractmethod
    def __iter__(self) -> Iterator[Frame]: ...

    def first(self) -> Frame:
        """Peek the first frame (for auto-seeding) without consuming the source."""
        return next(iter(self))


class ArrayFrameSource(FrameSource):
    """In-memory frames at a fixed fps (synthetic tests / already-decoded clips)."""
    def __init__(self, imgs: List[np.ndarray], fps: float):
        self._imgs = imgs
        self._fps = float(fps)

    @property
    def fps(self) -> float:
        return self._fps

    def __iter__(self) -> Iterator[Frame]:
        dt = 1.0 / self._fps
        for i, im in enumerate(self._imgs):
            yield Frame(i * dt, im)


class PyAVDecoder(FrameSource):
    """Frame-accurate decode via PyAV. Uses real per-frame timestamps and tolerates
    variable frame rate (phone video) — the decode layer we won't have to replace.

    Applies the stream's DISPLAY ROTATION (`frame.rotation`) so portrait phone clips
    decode UPRIGHT. iPhone stores the landscape sensor frame plus a display matrix
    (e.g. rotation=-90 for a portrait capture); without honouring it the bar moves
    along the image X-axis while the rep segmenter reads Y → the track looks static and
    the count collapses (the 06-13 DL-1..5 failure). Rotating here fixes it once for
    every downstream consumer (tracker, scale, segmenter)."""
    def __init__(self, path: str):
        self.path = str(path)
        self._fps = self._probe_fps()

    def _probe_fps(self) -> float:
        import av
        with av.open(self.path) as c:
            s = c.streams.video[0]
            r = s.average_rate or s.guessed_rate
            return float(r) if r else 30.0

    @property
    def fps(self) -> float:
        return self._fps

    @staticmethod
    def _apply_rotation(img: np.ndarray, rotation) -> np.ndarray:
        """Rotate a decoded BGR frame upright given `frame.rotation` (degrees).
        ffmpeg/PyAV convention: rotation -90 (=270) → rotate clockwise to display."""
        r = int(round(rotation or 0)) % 360
        if r % 90 != 0 or r == 0:
            return img
        # np.rot90 k is COUNTER-clockwise. Verified empirically: rotation -90 (=270)
        # → k=3 reproduces a clockwise display rotation (upright). So k = r // 90.
        return np.ascontiguousarray(np.rot90(img, (r // 90) % 4))

    def __iter__(self) -> Iterator[Frame]:
        import av
        dt = 1.0 / self._fps
        with av.open(self.path) as c:
            s = c.streams.video[0]
            for i, frame in enumerate(c.decode(s)):
                t = frame.time
                if t is None:                 # rare: rebuild from index
                    t = i * dt
                img = self._apply_rotation(frame.to_ndarray(format="bgr24"),
                                           getattr(frame, "rotation", 0))
                yield Frame(float(t), img)
