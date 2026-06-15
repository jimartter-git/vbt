# The investor one-pager (3 pages, laminate-grade)

`meVBT-onepager.pdf` is the hand-out / laminate artifact; `meVBT-onepager.html`
is the same document as a single self-contained file (images embedded — prints
identically from any browser). Built 2026-06-11.

## What's in it

- **Page 1 — the thesis.** New logo + masthead, the HR-blind-spot story, headline
  stats, and the **annotated deadlift hero frame**: every overlay (bar path, plate
  ring, ZUPT marker, decoy rejection, 0.66 m/s readout) is the real output of
  `vbt_video`'s FlowTracker on that clip — nothing illustrative.
- **Page 2 — the proof.** The comparison table vs SmartBarbell and Vitruve from the
  frozen 2026-06-11 benchmark (reps 0.32 vs 2.57; velocity-loss 3.2pp vs 9.0pp),
  annotated squat (decoy/clutter story) + near-failure bench frames, and the
  per-rep fatigue chart for BN-4 (the terminal rep SmartBarbell loses).
- **Page 3 — the platform.** Fusion architecture, the white space (per-rep
  confidence, muscular strain score), the dataset lab, roadmap, the science, and
  an honest-limits box.

## Rebuild

```bash
pip install -r analysis/requirements-video.txt pillow scipy   # tracker deps
apt-get install -y fonts-inter && pip install weasyprint      # PDF (optional)
python docs/onepager/build.py            # add --preview for page PNGs
```

The script extracts the three hero frames from `dataset/raw`, re-runs the
tracker for the bar-path overlays, and regenerates both files. Scoreboard
numbers are constants from `docs/cv-fusion.md` → "Full scoreboard snapshot
(2026-06-11)" — update them there first, then here, if the benchmark moves.

`logo.svg` / `logo-dark.svg` — the standalone mark: plate ring + one rep's
bar path forming the V, amber dot = the ZUPT moment (v=0 at the turnaround).
