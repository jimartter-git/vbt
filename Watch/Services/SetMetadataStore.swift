import Foundation
import VBTCore

/// Persists the last-used `SetMetadata` across sets and workouts, so the
/// second tagged set of a workout defaults to the first's tags — the "matches
/// what you had last provided" behavior. Also maintains a per-(date, lift)
/// auto-increment counter so the app can suggest set index 1, 2, 3 as the
/// lifter runs through a lift, and reset when the lift changes or a new day
/// starts.
///
/// UserDefaults-backed (small values, no schema concerns). Isolated to
/// `@MainActor` so the UI can read/write directly.
@MainActor
final class SetMetadataStore: ObservableObject {

    static let shared = SetMetadataStore()

    private let defaults: UserDefaults
    private let calendar: Calendar

    init(defaults: UserDefaults = .standard, calendar: Calendar = .current) {
        self.defaults = defaults
        self.calendar = calendar
    }

    // MARK: - Sticky defaults

    private static let lastMetadataKey = "vbt.setMetadata.last.v1"

    /// The sticky metadata suggested for a new set — last-used values with
    /// `setIndex` bumped and `notes` cleared (a note is per-set-specific).
    func nextSuggestedMetadata(for date: Date = Date()) -> SetMetadata {
        var meta = loadLast() ?? SetMetadata()
        meta.setIndex = nextSetIndex(for: meta.lift, on: date, customCode: meta.customLiftCode)
        meta.notes = nil
        return meta
    }

    /// Persist the metadata the user just tagged. Called at the moment the set
    /// STARTS recording so a crash still leaves the sticky state useful.
    func remember(_ meta: SetMetadata, on date: Date = Date()) {
        saveLast(meta)
        // Reserve this index so `nextSuggestedMetadata` on the same lift-day
        // returns index + 1 next time.
        recordUse(of: meta.effectiveLiftCode, on: date, index: meta.setIndex)
    }

    // MARK: - Set-index counter (per date + lift code)

    private static let setIndexKeyPrefix = "vbt.setIndex.v1."

    /// Returns the next 1-based set index for the given lift on the given
    /// local date — one more than the highest recorded, or 1 if the lift is
    /// new to that day.
    func nextSetIndex(for lift: Lift, on date: Date, customCode: String? = nil) -> Int {
        let code = (lift == .other ? (customCode?.uppercased() ?? "OTHER") : lift.code)
        return nextSetIndex(forCode: code, on: date)
    }

    private func nextSetIndex(forCode code: String, on date: Date) -> Int {
        let last = defaults.integer(forKey: setIndexKey(code: code, date: date))
        return last + 1
    }

    private func recordUse(of code: String, on date: Date, index: Int) {
        let key = setIndexKey(code: code, date: date)
        let existing = defaults.integer(forKey: key)
        // Keep the highest — if the user manually set 5, then does 3, we still
        // suggest 6 next (the user is filling in gaps, not resetting).
        if index > existing {
            defaults.set(index, forKey: key)
        }
    }

    private func setIndexKey(code: String, date: Date) -> String {
        let ymd = LocalDateFormatter().string(from: date, in: calendar)
        return Self.setIndexKeyPrefix + "\(ymd).\(code)"
    }

    // MARK: - JSON blob

    private func loadLast() -> SetMetadata? {
        guard let data = defaults.data(forKey: Self.lastMetadataKey) else { return nil }
        return try? JSONDecoder().decode(SetMetadata.self, from: data)
    }

    private func saveLast(_ meta: SetMetadata) {
        guard let data = try? JSONEncoder().encode(meta) else { return }
        defaults.set(data, forKey: Self.lastMetadataKey)
    }
}
