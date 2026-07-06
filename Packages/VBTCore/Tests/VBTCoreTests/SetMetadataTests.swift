import XCTest
@testable import VBTCore

/// Locks the filename convention — a change here shifts every downstream
/// ingest tool (`analysis/scripts/coverage.py`, `dataset/tools/*`).
final class SetMetadataTests: XCTestCase {

    func testVelocitySetFileStemMatchesDatasetConvention() throws {
        // 2026-06-16 in America/Los_Angeles (typical lifter timezone). Expect
        // `20260616-BN-3_watch` regardless of the UTC hour.
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let date = cal.date(from: DateComponents(year: 2026, month: 6, day: 16, hour: 22, minute: 30))!

        let meta = SetMetadata(lift: .bench, setIndex: 3)
        XCTAssertEqual(meta.velocitySetFileStem(on: date, calendar: cal), "20260616-BN-3_watch")
    }

    func testEveryLiftCodeIsUnique() {
        let codes = Lift.allCases.map(\.code)
        XCTAssertEqual(codes.count, Set(codes).count,
                       "Lift codes must be unique (they end up in filenames).")
    }

    func testCustomLiftCodeUsedForOther() {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let date = cal.date(from: DateComponents(year: 2026, month: 7, day: 6))!

        let meta = SetMetadata(lift: .other, customLiftCode: "ohp", setIndex: 2)
        XCTAssertEqual(meta.velocitySetFileStem(on: date, calendar: cal), "20260706-OHP-2_watch")
    }

    func testWorkoutHRFileStem() {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let date = cal.date(from: DateComponents(year: 2026, month: 7, day: 6))!

        XCTAssertEqual(workoutHRFileStem(on: date, calendar: cal), "20260706-workout_hr")
        XCTAssertEqual(workoutHRFileStem(on: date, calendar: cal, workoutOrdinal: 2),
                       "20260706-workout_hr-2")
    }

    func testRecordingMetadataFileStemRoutesByKind() {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let date = cal.date(from: DateComponents(year: 2026, month: 7, day: 6, hour: 10))!

        let setMeta = SetMetadata(lift: .deadlift, setIndex: 1)
        let velocity = RecordingMetadata(
            kind: .velocitySet,
            startedAt: date,
            exercise: "deadlift",
            setMetadata: setMeta
        )
        // NB: legacy stem uses UTC, but the modern stem uses the caller's
        // calendar. We check the modern one here.
        XCTAssertTrue(velocity.fileStem.hasSuffix("-DL-1_watch"))

        let hr = RecordingMetadata(
            kind: .workoutHR,
            startedAt: date,
            exercise: "workout"
        )
        XCTAssertTrue(hr.fileStem.hasSuffix("-workout_hr"))
    }
}
