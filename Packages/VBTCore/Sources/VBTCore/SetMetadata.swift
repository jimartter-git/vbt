import Foundation

/// Canonical lift codes — MUST match the filename convention used across the
/// dataset (`dataset/raw/<YYYYMMDD>-<CODE>-<N>_watch.csv`) and the `sets.csv`
/// `lift` column ("squat", "bench", etc.).
public enum Lift: String, Codable, CaseIterable, Sendable {
    case squat        = "squat"
    case bench        = "bench"
    case deadlift     = "deadlift"
    case inclineBench = "incline_bench"
    case row          = "row"
    case rdl          = "rdl"
    case skullCrusher = "skull_crusher"
    case other        = "other"

    /// Short code that appears in the filename (`BN`, `DL`, ...). Matches
    /// existing files in `dataset/raw/` — extending this set must extend those
    /// tools too (`analysis/scripts/coverage.py`, ingestion helpers).
    public var code: String {
        switch self {
        case .squat:        return "SQ"
        case .bench:        return "BN"
        case .deadlift:     return "DL"
        case .inclineBench: return "IB"
        case .row:          return "ROW"
        case .rdl:          return "RDL"
        case .skullCrusher: return "SC"
        case .other:        return "OTHER"
        }
    }

    public var displayName: String {
        switch self {
        case .squat:        return "Squat"
        case .bench:        return "Bench"
        case .deadlift:     return "Deadlift"
        case .inclineBench: return "Incline Bench"
        case .row:          return "Row"
        case .rdl:          return "RDL"
        case .skullCrusher: return "Skull Crusher"
        case .other:        return "Other"
        }
    }
}

/// Where the watch is worn / mounted for this set. Defaults to `wrist`; the
/// `bar` future mount is not physically supported yet but reserved so a set
/// captured under it is unambiguous downstream.
public enum WatchMount: String, Codable, CaseIterable, Sendable {
    case wrist
    case bar

    public var displayName: String {
        switch self {
        case .wrist: return "Wrist"
        case .bar:   return "Bar"
        }
    }
}

/// Plate profile at the working weight. Used by the CV path (bumper vs iron vs
/// hex changes rim measurement; see `docs/cv-fusion.md`) — logged on the
/// watch side so the CV pipeline can key off the tag when a video exists for
/// the same set.
public enum PlateType: String, Codable, CaseIterable, Sendable {
    case unknown
    case bumper
    case iron
    case hex
    case deepDish

    public var displayName: String {
        switch self {
        case .unknown:  return "Unknown"
        case .bumper:   return "Bumper"
        case .iron:     return "Iron"
        case .hex:      return "Hex"
        case .deepDish: return "Deep dish"
        }
    }
}

/// Everything the user tags on a velocity set. `lift` + `setIndex` + `date`
/// are the file-naming inputs (via `fileStem(...)` below). The rest are
/// carried into the JSON sidecar for later analysis.
public struct SetMetadata: Codable, Equatable, Sendable {
    public var lift: Lift
    /// User-typed short code when `lift == .other` (e.g. "OHP", "curl"). Used
    /// in the filename in place of `Lift.code`.
    public var customLiftCode: String?
    /// 1-indexed set number within this lift-day (`BN-1`, `BN-2`, ...). The
    /// watch UI auto-suggests the next value from `SetMetadataStore` but the
    /// user can override.
    public var setIndex: Int
    public var mount: WatchMount
    /// Rate of Perceived Exertion, 0.5-step (typical range 6.0–10.0). `nil`
    /// = user didn't record one.
    public var rpe: Double?
    /// Working load. Unit is user-selectable; stored explicitly to avoid the
    /// lb/kg confusion that has bitten dataset ingest.
    public var load: Double?
    public var loadUnit: LoadUnit
    public var plateType: PlateType
    /// Free-text notes ("last back-off", "grinder", "belt on"). Optional.
    public var notes: String?

    public enum LoadUnit: String, Codable, CaseIterable, Sendable {
        case lb, kg
        public var displayName: String { rawValue }
    }

    public init(
        lift: Lift = .squat,
        customLiftCode: String? = nil,
        setIndex: Int = 1,
        mount: WatchMount = .wrist,
        rpe: Double? = nil,
        load: Double? = nil,
        loadUnit: LoadUnit = .lb,
        plateType: PlateType = .unknown,
        notes: String? = nil
    ) {
        self.lift = lift
        self.customLiftCode = customLiftCode
        self.setIndex = setIndex
        self.mount = mount
        self.rpe = rpe
        self.load = load
        self.loadUnit = loadUnit
        self.plateType = plateType
        self.notes = notes
    }

    /// The lift code that ends up in the filename — respects the free-text
    /// `customLiftCode` when the user picked `.other`.
    public var effectiveLiftCode: String {
        if lift == .other, let custom = customLiftCode?.uppercased(), !custom.isEmpty {
            return custom
        }
        return lift.code
    }

    /// Filename stem for a velocity-set recording, matching the dataset
    /// convention `<YYYYMMDD>-<CODE>-<N>_watch` (e.g. `20260616-BN-3_watch`).
    /// `date` is passed in explicitly so callers control the timezone; the
    /// watch always uses the LOCAL date the lifter is in, since a set at 11pm
    /// local should file under that day even if UTC has ticked over.
    public func velocitySetFileStem(on date: Date, calendar: Calendar = .current) -> String {
        let ymd = Self.filenameDateFormatter.string(from: date, in: calendar)
        return "\(ymd)-\(effectiveLiftCode)-\(setIndex)_watch"
    }
}

/// Filename stem for the workout-wide HR sidecar. `<YYYYMMDD>-workout_hr`
/// (one per workout; a second workout the same day gets `-workout_hr-2`).
public func workoutHRFileStem(
    on date: Date,
    calendar: Calendar = .current,
    workoutOrdinal: Int = 1
) -> String {
    let ymd = SetMetadata.filenameDateFormatter.string(from: date, in: calendar)
    return workoutOrdinal <= 1
        ? "\(ymd)-workout_hr"
        : "\(ymd)-workout_hr-\(workoutOrdinal)"
}

extension SetMetadata {
    /// `YYYYMMDD` in the caller-supplied calendar (local by default).
    fileprivate static let filenameDateFormatter = LocalDateFormatter()
}

/// Small wrapper so we can format `YYYYMMDD` in a specific `Calendar` without
/// stashing a shared `DateFormatter` tied to one timezone.
public struct LocalDateFormatter {
    public init() {}
    public func string(from date: Date, in calendar: Calendar) -> String {
        let comps = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d%02d%02d",
                      comps.year ?? 0, comps.month ?? 0, comps.day ?? 0)
    }
}
