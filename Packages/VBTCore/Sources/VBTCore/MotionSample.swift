import Foundation

/// One device-motion sample, mirroring `CMDeviceMotion`'s fields we care about.
///
/// This is the on-the-wire / on-disk contract shared by the watch (producer),
/// the phone (relay), and the Python analysis pipeline (consumer). It MUST stay
/// in lock-step with `docs/data-schema.md` and `analysis/vbt_analysis/ingest.py`.
///
/// Units: `ua*` and `g*` are in g (gravity already removed from `ua`);
/// `q*` is a unit quaternion (attitude); `t` is `CMDeviceMotion.timestamp`
/// (seconds since device boot — monotonic, not wall clock, not cross-device).
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

    public init(
        t: Double,
        uaX: Double, uaY: Double, uaZ: Double,
        gX: Double, gY: Double, gZ: Double,
        qW: Double, qX: Double, qY: Double, qZ: Double
    ) {
        self.t = t
        self.uaX = uaX; self.uaY = uaY; self.uaZ = uaZ
        self.gX = gX; self.gY = gY; self.gZ = gZ
        self.qW = qW; self.qX = qX; self.qY = qY; self.qZ = qZ
    }
}
