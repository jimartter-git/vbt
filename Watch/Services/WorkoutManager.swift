import Foundation
import HealthKit

/// Owns the `HKWorkoutSession` whose sole job in the PoC is to keep the motion
/// sensors alive and prevent the watch from sleeping mid-set. We don't care
/// about the saved workout itself yet — just the live session it provides.
@MainActor
final class WorkoutManager: NSObject, ObservableObject {
    private let healthStore = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?

    /// Ask for the minimal HealthKit permissions needed to run a workout.
    func requestAuthorization() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw WorkoutError.healthDataUnavailable
        }
        let workoutType = HKObjectType.workoutType()
        try await healthStore.requestAuthorization(
            toShare: [workoutType],
            read: [workoutType]
        )
    }

    func start() throws {
        let config = HKWorkoutConfiguration()
        config.activityType = .traditionalStrengthTraining
        config.locationType = .indoor

        let session = try HKWorkoutSession(healthStore: healthStore, configuration: config)
        let builder = session.associatedWorkoutBuilder()
        builder.dataSource = HKLiveWorkoutDataSource(
            healthStore: healthStore,
            workoutConfiguration: config
        )

        self.session = session
        self.builder = builder

        let startDate = Date()
        session.startActivity(with: startDate)
        builder.beginCollection(withStart: startDate) { _, _ in }
    }

    func stop() {
        guard let session, let builder else { return }
        session.end()
        builder.endCollection(withEnd: Date()) { [weak self] _, _ in
            builder.finishWorkout { _, _ in }
            self?.session = nil
            self?.builder = nil
        }
    }

    enum WorkoutError: Error { case healthDataUnavailable }
}
