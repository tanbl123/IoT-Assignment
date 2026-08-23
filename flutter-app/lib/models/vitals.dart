/// One vitals snapshot, matching the Firebase shape written by the backend:
///   telemetry/latest     : { hr, spo2, status, ts, ... }
///   all_records/<pushId> : { record_type, hr, spo2, status, ts, ... }
/// Extra fields (accel_g, tilt, record_type, features, …) are ignored here.
class Vitals {
  final int hr;
  final int spo2;
  final String status;
  final int ts; // unix seconds

  const Vitals({
    required this.hr,
    required this.spo2,
    required this.status,
    required this.ts,
  });

  // ts may be seconds (10 digits, from the Python backend) or milliseconds
  // (13 digits, from older writers). Normalise both to a real DateTime.
  DateTime get time => DateTime.fromMillisecondsSinceEpoch(
        ts > 1000000000000 ? ts : ts * 1000,
      );

  /// Firebase returns a Map<Object?, Object?>; numbers may arrive as int,
  /// double or String, so parse defensively.
  factory Vitals.fromMap(Map<dynamic, dynamic> m) {
    int asInt(dynamic v) =>
        v is int ? v : (v is double ? v.round() : int.tryParse("$v") ?? -1);
    return Vitals(
      hr: asInt(m["hr"]),
      spo2: asInt(m["spo2"]),
      status: (m["status"] ?? "UNKNOWN").toString(),
      ts: asInt(m["ts"]),
    );
  }
}
