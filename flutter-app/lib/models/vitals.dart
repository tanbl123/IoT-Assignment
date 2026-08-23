/// One sensor snapshot, matching the Firebase shape written by the backend:
///   telemetry/latest     : { hr, spo2, status, accel_g, tilt, lat, lng, ts, ... }
///   all_records/<pushId> : { record_type, hr, spo2, status, accel_g, tilt, ts, ... }
///
/// Missing/invalid numeric fields use -1 as a sentinel so charts and tiles can
/// skip them (real hr/spo2/accel/tilt are always >= 0).
class Vitals {
  final int hr;
  final int spo2;
  final String status;
  final double accelG; // acceleration magnitude in g (~1.0 at rest)
  final double tilt; // tilt angle in degrees
  final double lat;
  final double lng;
  final int ts; // unix seconds or milliseconds

  const Vitals({
    required this.hr,
    required this.spo2,
    required this.status,
    required this.accelG,
    required this.tilt,
    required this.lat,
    required this.lng,
    required this.ts,
  });

  bool get hasGps => lat != 0.0 || lng != 0.0;

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
    double asDouble(dynamic v, double dflt) => v == null
        ? dflt
        : (v is num ? v.toDouble() : double.tryParse("$v") ?? dflt);
    return Vitals(
      hr: asInt(m["hr"]),
      spo2: asInt(m["spo2"]),
      status: (m["status"] ?? "UNKNOWN").toString(),
      accelG: asDouble(m["accel_g"], -1), // -1 = field absent
      tilt: asDouble(m["tilt"], -1),
      lat: asDouble(m["lat"], 0),
      lng: asDouble(m["lng"], 0),
      ts: asInt(m["ts"]),
    );
  }
}
