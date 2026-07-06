import Foundation
import HealthKit
import os

/// Owns the `HKWorkoutSession` whose primary job is keeping the motion sensors
/// alive through a set. The associated `HKLiveWorkoutBuilder` also collects
/// heart-rate + active-energy samples and, on `stop()`, persists an
/// `HKWorkout` to Apple Health — which is what makes the set visible to
/// third-party HR/strain apps (Athlytic, Whoop) that read HealthKit.
@MainActor
final class WorkoutManager: NSObject, ObservableObject {
    private let healthStore = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?
    private let log = Logger(subsystem: "com.vbt.app.watchkitapp", category: "workout")

    /// HK permissions.
    /// - Read: HR + active energy so `HKLiveWorkoutDataSource` actually attaches
    ///   those samples to the workout (silently drops them without read auth).
    /// - Share: workout type + active energy so the finished `HKWorkout` +
    ///   its energy total land in Apple Health for downstream apps to ingest.
    func requestAuthorization() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw WorkoutError.healthDataUnavailable
        }
        let workoutType = HKObjectType.workoutType()
        let heartRate = HKQuantityType(.heartRate)
        let activeEnergy = HKQuantityType(.activeEnergyBurned)
        try await healthStore.requestAuthorization(
            toShare: [workoutType, activeEnergy],
            read: [workoutType, heartRate, activeEnergy]
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
        builder.beginCollection(withStart: startDate) { [log] success, error in
            if !success {
                log.error("beginCollection failed: \(error?.localizedDescription ?? "unknown", privacy: .public)")
            }
        }
    }

    func stop() {
        guard let session, let builder else { return }
        session.end()
        builder.endCollection(withEnd: Date()) { [weak self, log] success, error in
            if !success {
                log.error("endCollection failed: \(error?.localizedDescription ?? "unknown", privacy: .public)")
            }
            builder.finishWorkout { workout, error in
                if let workout {
                    log.info("HKWorkout saved: \(workout.uuid, privacy: .public)")
                } else {
                    log.error("finishWorkout failed: \(error?.localizedDescription ?? "unknown", privacy: .public)")
                }
            }
            self?.session = nil
            self?.builder = nil
        }
    }

    enum WorkoutError: Error { case healthDataUnavailable }
}
