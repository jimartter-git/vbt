import Foundation
import WatchKit
import VBTCore

/// Serializes captured samples to a CSV (+ JSON metadata sidecar) in a temp
/// directory, ready for `transferFile` to the phone. Format owned by VBTCore.
enum SessionWriter {
    static func write(
        samples: [MotionSample],
        exercise: String,
        rateHint: Int,
        notes: String? = nil
    ) throws -> (csv: URL, json: URL, metadata: RecordingMetadata) {
        let device = WKInterfaceDevice.current()
        let meta = RecordingMetadata(
            exercise: exercise,
            sampleRateHintHz: rateHint,
            deviceModel: device.model,
            osVersion: device.systemVersion,
            sampleCount: samples.count,
            notes: notes
        )

        let dir = FileManager.default.temporaryDirectory
        let csvURL = dir.appendingPathComponent("\(meta.fileStem).csv")
        let jsonURL = dir.appendingPathComponent("\(meta.fileStem).json")

        let csv = MotionSampleCSV.encode(samples)
        try Data(csv.utf8).write(to: csvURL, options: .atomic)

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(meta).write(to: jsonURL, options: .atomic)

        return (csvURL, jsonURL, meta)
    }
}
