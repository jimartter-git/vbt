import Foundation

/// CSV (de)serialization for `MotionSample` — the PoC wire format.
///
/// Column order is fixed and must match `docs/data-schema.md` and the Python
/// `ingest.COLUMNS`. A binary format is the documented upgrade path; when added
/// it lives behind this same type so call sites don't change.
public enum MotionSampleCSV {

    /// The exact header line (and column order) of a recording CSV.
    public static let header = "t,ua_x,ua_y,ua_z,g_x,g_y,g_z,q_w,q_x,q_y,q_z"

    /// Format one sample as a CSV row (no trailing newline).
    ///
    /// Uses a fixed decimal precision rather than the default `Double`
    /// description to keep files compact and locale-independent.
    public static func row(for s: MotionSample) -> String {
        func f(_ v: Double, _ p: Int = 6) -> String { String(format: "%.\(p)f", v) }
        // Timestamp keeps more precision (it's large-magnitude seconds).
        return [
            f(s.t, 6),
            f(s.uaX), f(s.uaY), f(s.uaZ),
            f(s.gX), f(s.gY), f(s.gZ),
            f(s.qW), f(s.qX), f(s.qY), f(s.qZ),
        ].joined(separator: ",")
    }

    /// Encode samples into a full CSV document (header + rows + trailing NL).
    public static func encode(_ samples: [MotionSample]) -> String {
        var out = header
        out.reserveCapacity(samples.count * 96)
        for s in samples {
            out += "\n"
            out += row(for: s)
        }
        out += "\n"
        return out
    }

    /// Parse a CSV document back into samples. Tolerant of a missing/changed
    /// header (matched by name) and of trailing blank lines.
    public static func decode(_ text: String) throws -> [MotionSample] {
        var lines = text.split(whereSeparator: \.isNewline).map(String.init)
        guard !lines.isEmpty else { return [] }

        // Resolve column indices from the header if present.
        let expected = header.split(separator: ",").map(String.init)
        var indexFor = [String: Int]()
        if lines[0].contains("ua_x") {
            for (i, name) in lines[0].split(separator: ",").map(String.init).enumerated() {
                indexFor[name] = i
            }
            lines.removeFirst()
        } else {
            for (i, name) in expected.enumerated() { indexFor[name] = i }
        }
        for name in expected where indexFor[name] == nil {
            throw CSVError.missingColumn(name)
        }

        return try lines.compactMap { line -> MotionSample? in
            if line.isEmpty { return nil }
            let cols = line.split(separator: ",", omittingEmptySubsequences: false).map(String.init)
            func val(_ name: String) throws -> Double {
                let i = indexFor[name]!
                guard i < cols.count, let d = Double(cols[i]) else {
                    throw CSVError.badRow(line)
                }
                return d
            }
            return MotionSample(
                t: try val("t"),
                uaX: try val("ua_x"), uaY: try val("ua_y"), uaZ: try val("ua_z"),
                gX: try val("g_x"), gY: try val("g_y"), gZ: try val("g_z"),
                qW: try val("q_w"), qX: try val("q_x"), qY: try val("q_y"), qZ: try val("q_z")
            )
        }
    }

    public enum CSVError: Error, Equatable {
        case missingColumn(String)
        case badRow(String)
    }
}
