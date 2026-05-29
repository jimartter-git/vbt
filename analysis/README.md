# VBT analysis pipeline

Offline rep detection + ZUPT velocity estimation for wrist-IMU recordings, and
watch-vs-Vitruve calibration. This is where the estimator is iterated; the
proven algorithm later gets ported to the Swift `VBTCore` package.

## Setup

```bash
cd analysis
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Try it without a watch (synthetic)

```bash
python scripts/analyze_session.py --demo --out demo.png
```

Prints per-rep mean/peak velocity + velocity loss for a synthetic 5-rep set and
saves accel/velocity plots.

## Analyze a real recording

Pull `<sessionId>.csv` off the phone (share sheet) into `data/`, then:

```bash
python scripts/analyze_session.py data/<sessionId>.csv --out session.png
```

## Compare against Vitruve

Align watch reps to Vitruve reps by index (see
`../docs/calibration-protocol.md`) and use `vbt_analysis.compare_vitruve`:

```python
from vbt_analysis.compare_vitruve import plot_comparison
stats = plot_comparison(watch_mv, vitruve_mv, out_path="calibration.png")
print(stats)   # bias, RMSE, r, Bland-Altman limits, regression fit
```

## Tests

```bash
pytest -q
```

Tests validate the integration/ZUPT math against synthetic ground truth (true
mean concentric velocity = peak × 2/π). Real-data accuracy is answered by
Vitruve calibration, not these tests.

## Layout

```
analysis/
├── vbt_analysis/
│   ├── ingest.py           load CSV (schema) / generate synthetic sets
│   ├── rep_detect.py       turnaround (ZUPT-anchor) detection
│   ├── velocity.py         vertical projection, ZUPT integration, per-rep metrics
│   └── compare_vitruve.py  watch-vs-Vitruve stats + plots
├── scripts/analyze_session.py
├── tests/test_velocity.py
└── data/                   recorded sessions (gitignored)
```
