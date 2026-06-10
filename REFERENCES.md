# Project References

Key references for this Apple Watch IMU-based velocity-based training (VBT) project. Each entry includes why it matters — read the "Why" before deciding to dig in.

## Tier 1: Essential, Directly Actionable

### Achermann et al. 2023 — Apple Watch VBT validation
- **Citation:** Achermann, B., Oberhofer, K., Ferguson, S. J., & Lorenzetti, S. R. (2023). Velocity-Based Strength Training: The Validity and Personal Monitoring of Barbell Velocity with the Apple Watch. *Sports*, 11(7), 125.
- **DOI:** 10.3390/sports11070125
- **Link:** https://www.mdpi.com/2075-4663/11/7/125
- **Full text (PMC):** https://pmc.ncbi.nlm.nih.gov/articles/PMC10383699/
- **Why:** The methodology blueprint for this project. Validated Apple Watch IMU against Vicon motion capture during back squats. Bar-mounted Watch achieved r = 0.971–0.979 for mean velocity (SEE = 0.049 m/s), beating a commercial $400 IMU device. Wrist-worn achieved r = 0.952–0.965. **The supplementary materials contain their Python signal processing pipeline — read those, not just the abstract.** Use their accuracy figures as the validation target for our pipeline. Also documents a known slow-velocity segmentation issue that we should expect to encounter.

### Wojtek120/IMU-velocity-and-displacement-measurements — Open-source IMU VBT
- **Link:** https://github.com/Wojtek120/IMU-velocity-and-displacement-measurements
- **Companion library:** https://github.com/Wojtek120/MPU9250
- **Why:** Working open-source implementation of IMU-based velocity measurement for powerlifting. Arduino firmware + Android app + SQLite storage. Even though the platform differs from ours (Arduino → watchOS), the signal processing approach translates directly: Madgwick orientation filter + Zero Velocity Update (ZVU) drift correction. Read the firmware to understand the filtering pipeline before implementing our own. Includes calibration procedure for MEMS IMU offsets/scale factors — same calibration concepts apply to the Apple Watch.

## Tier 2: Useful Supporting References

### Apple Core Motion documentation
- **Link:** https://developer.apple.com/documentation/coremotion
- **Specifically:** `CMMotionManager`, `CMDeviceMotion`, `startDeviceMotionUpdates(using:to:withHandler:)`
- **Why:** The Watch IMU access layer. **Use `CMDeviceMotion` (fused, gravity-corrected, with orientation quaternion), not raw `CMAccelerometerData`.** Sample at 100 Hz to match the Achermann methodology. The `CMAttitude` quaternion in `CMDeviceMotion` is what lets us rotate accelerations into the world frame for vertical-velocity isolation.

### Madgwick 2010 — Sensor fusion algorithm
- **Citation:** Madgwick, S. O. H. (2010). An efficient orientation filter for inertial and inertial/magnetic sensor arrays. University of Bristol technical report.
- **Link:** https://x-io.co.uk/open-source-imu-and-ahrs-algorithms/
- **Why:** Canonical reference for IMU sensor fusion. Mature Swift ports exist on GitHub. Avoids the trap of reimplementing a worse Kalman filter from scratch. Note: `CMDeviceMotion` already does sensor fusion internally, so we may not need to implement Madgwick directly — but understanding it helps interpret what Apple's fused output represents and when we'd need to roll our own (e.g., for raw-sensor research mode).

### Renner, Mitter & Baca 2024 — VBT app validation benchmarks
- **Citation:** Renner, A., Mitter, B., & Baca, A. (2024). Concurrent validity of novel smartphone-based apps monitoring barbell velocity in powerlifting exercises. *PLOS ONE*, 19(11), e0313919.
- **DOI:** 10.1371/journal.pone.0313919
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC11575817
- **Why:** Validation of Qwik VBT, Metric, and MyLift against a RepOne linear position transducer across squat, bench, and deadlift. Provides concrete accuracy targets across multiple velocity metrics (mean, peak, propulsive) on actual powerlifting movements. Use as a secondary benchmark for our pipeline beyond Achermann.

## Tier 3: Deeper Reading (Optional)

### Balsalobre-Fernández, C. — Smartphone VBT methodology
- **Why:** Author of foundational validation work on smartphone-based velocity measurement (My Jump Lab / PowerLift lineage). His methodology papers establish the statistical validation framework that newer studies cite. Useful if we need to defend an accuracy claim or design a new validation protocol. Search Google Scholar for his name + "velocity" or "VBT".
