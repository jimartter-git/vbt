import Foundation

/// One device-motion sample, mirroring `CMDeviceMotion`'s fields we care about.
///
/// This is the on-the-wire / on-disk contract shared by the watch (producer),
/// the phone (relay), and the Python analysis pipeline (consumer). It MUST stay
/// in lock-step with `docs/data-schema.md` and `analysis/vbt_analysis/ingest.py`.
///
/// Units: `ua*` and `g*` are in g (gravity already removed from `ua`);
/// `q*` is a unit quaternion (attitude); `rr*` is the calibrated gyro
/// (rotation rate) in rad/s; `mf*` is the calibrated magnetic field in microtesla
/// (often low-accuracy indoors — see `docs/data-schema.md`); `t` is
/// `CMDeviceMotion.timestamp` (seconds since device boot — monotonic, not wall
/// clock, not cross-device).
///
/// `rr*`/`mf*` were ADDED after the first captures, so they are optional on the
/// wire (default 0): older recordings predate them and must still decode. The
/// gyro is the high-value addition — it enables orientation fusion (Madgwick) and
/// is the richest feature for a future learned rep/velocity model.
public struct MotionSample: Codable, Equatable, Sendable {
    public var t: Double
    public var uaX: Double
    public var uaY: Double
    public var uaZ: Double
    public var gX: Double
    public var gY: Double
    public var gZ: Double
    public var qW: Double
    public var qX: Double
    public var qY: Double
    public var qZ: Double
    // Calibrated gyro (rad/s) and magnetic field (µT). Optional/appended — see note above.
    public var rrX: Double
    public var rrY: Double
    public var rrZ: Double
    public var mfX: Double
    public var mfY: Double
    public var mfZ: Double

    public init(
        t: Double,
        uaX: Double, uaY: Double, uaZ: Double,
        gX: Double, gY: Double, gZ: Double,
        qW: Double, qX: Double, qY: Double, qZ: Double,
        rrX: Double = 0, rrY: Double = 0, rrZ: Double = 0,
        mfX: Double = 0, mfY: Double = 0, mfZ: Double = 0
    ) {
        self.t = t
        self.uaX = uaX; self.uaY = uaY; self.uaZ = uaZ
        self.gX = gX; self.gY = gY; self.gZ = gZ
        self.qW = qW; self.qX = qX; self.qY = qY; self.qZ = qZ
        self.rrX = rrX; self.rrY = rrY; self.rrZ = rrZ
        self.mfX = mfX; self.mfY = mfY; self.mfZ = mfZ
    }
}
