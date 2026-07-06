import Foundation

/// One heart-rate sample streamed alongside the outer workout. Written to the
/// workout-wide `<YYYYMMDD>-workout_hr.csv` sidecar so Python analysis can
/// slice HR by any velocity set's `[startedAt, stoppedAt]` window without
/// going through the HealthKit export dance on the Mac.
///
/// Two clocks: `t` shares the `CMDeviceMotion.timestamp` boot clock (so it
/// aligns natively with the IMU sample stream via the recording's clock
/// anchor), and `utc` is the wall-clock reading at the sample time (redundant,
/// but robust: if the anchor is ever lost we can still slice by wall-clock).
public struct HeartRateSample: Codable, Equatable, Sendable {
    /// Device uptime (seconds since boot) at the sample.
    public var t: Double
    /// Wall-clock UTC at the sample (`hkSample.startDate`).
    public var utc: Date
    /// Beats per minute.
    public var bpm: Double

    public init(t: Double, utc: Date, bpm: Double) {
        self.t = t
        self.utc = utc
        self.bpm = bpm
    }
}

/// CSV encoder/decoder for the workout HR sidecar. Kept trivial — the file is
/// small (a 60-min workout at 1 Hz ≈ 3600 rows).
public enum HeartRateSampleCSV {
    public static let header = "t,utc,bpm"

    private static let utcFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    public static func encode(_ samples: [HeartRateSample]) -> String {
        var out = header + "\n"
        out.reserveCapacity(samples.count * 40 + header.count + 1)
        for s in samples {
            out += "\(s.t),\(utcFormatter.string(from: s.utc)),\(s.bpm)\n"
        }
        return out
    }

    public static func decode(_ csv: String) -> [HeartRateSample] {
        var rows: [HeartRateSample] = []
        var isFirst = true
        for line in csv.split(separator: "\n") {
            if isFirst { isFirst = false; continue }
            let parts = line.split(separator: ",", omittingEmptySubsequences: false)
            guard parts.count == 3,
                  let t = Double(parts[0]),
                  let utc = utcFormatter.date(from: String(parts[1])),
                  let bpm = Double(parts[2]) else { continue }
            rows.append(HeartRateSample(t: t, utc: utc, bpm: bpm))
        }
        return rows
    }
}
