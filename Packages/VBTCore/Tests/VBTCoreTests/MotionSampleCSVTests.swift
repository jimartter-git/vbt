import XCTest
@testable import VBTCore

final class MotionSampleCSVTests: XCTestCase {

    private func sample(_ t: Double) -> MotionSample {
        MotionSample(
            t: t,
            uaX: 0.01, uaY: -0.02, uaZ: 0.5,
            gX: 0, gY: 0, gZ: -1,
            qW: 1, qX: 0, qY: 0, qZ: 0
        )
    }

    func testHeaderMatchesContract() {
        XCTAssertEqual(
            MotionSampleCSV.header,
            "t,ua_x,ua_y,ua_z,g_x,g_y,g_z,q_w,q_x,q_y,q_z"
        )
    }

    func testEncodeStartsWithHeaderAndHasRowPerSample() {
        let csv = MotionSampleCSV.encode([sample(0), sample(0.005)])
        let lines = csv.split(whereSeparator: \.isNewline)
        XCTAssertEqual(lines.first.map(String.init), MotionSampleCSV.header)
        XCTAssertEqual(lines.count, 3) // header + 2 rows
    }

    func testRoundTripPreservesValues() throws {
        let original = [sample(123.456), sample(123.461), sample(123.466)]
        let decoded = try MotionSampleCSV.decode(MotionSampleCSV.encode(original))
        XCTAssertEqual(decoded.count, original.count)
        for (a, b) in zip(decoded, original) {
            XCTAssertEqual(a.t, b.t, accuracy: 1e-5)
            XCTAssertEqual(a.uaZ, b.uaZ, accuracy: 1e-5)
            XCTAssertEqual(a.gZ, b.gZ, accuracy: 1e-5)
            XCTAssertEqual(a.qW, b.qW, accuracy: 1e-5)
        }
    }

    func testDecodeToleratesMissingHeader() throws {
        let body = MotionSampleCSV.row(for: sample(1.0))
        let decoded = try MotionSampleCSV.decode(body + "\n")
        XCTAssertEqual(decoded.count, 1)
        XCTAssertEqual(decoded[0].uaZ, 0.5, accuracy: 1e-5)
    }

    func testDecodeRejectsBadRow() {
        let bad = MotionSampleCSV.header + "\n1.0,2.0,3.0\n" // too few columns
        XCTAssertThrowsError(try MotionSampleCSV.decode(bad))
    }
}

final class SetSummaryTests: XCTestCase {
    func testVelocityLossPct() {
        let reps = [0.80, 0.72, 0.60].enumerated().map { i, mv in
            RepMetrics(
                repIndex: i, startTime: 0, turnaroundTime: 0, endTime: 0,
                meanConcentricVelocity: mv, peakConcentricVelocity: mv * 1.5,
                rangeOfMotion: 0.5
            )
        }
        let summary = SetSummary(reps: reps)
        XCTAssertEqual(summary.velocityLossPct, 25.0, accuracy: 0.001) // (0.8-0.6)/0.8
    }
}
