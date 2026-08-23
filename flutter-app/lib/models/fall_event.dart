/// One confirmed fall, matching the Firebase shape written by the backend:
///   fall_events/<pushId> : { hr, spo2, lat, lng, ts, status }
class FallEvent {
  final String id; // Firebase push key
  final int hr;
  final int spo2;
  final double lat;
  final double lng;
  final int ts; // unix seconds
  final String status;

  const FallEvent({
    required this.id,
    required this.hr,
    required this.spo2,
    required this.lat,
    required this.lng,
    required this.ts,
    required this.status,
  });

  // ts may be seconds (10 digits, from the Python backend) or milliseconds
  // (13 digits, from older writers). Normalise both to a real DateTime.
  DateTime get time => DateTime.fromMillisecondsSinceEpoch(
        ts > 1000000000000 ? ts : ts * 1000,
      );

  factory FallEvent.fromMap(String id, Map<dynamic, dynamic> m) {
    int asInt(dynamic v) =>
        v is int ? v : (v is double ? v.round() : int.tryParse("$v") ?? -1);
    double asDouble(dynamic v) =>
        v is double ? v : (v is int ? v.toDouble() : double.tryParse("$v") ?? 0.0);
    return FallEvent(
      id: id,
      hr: asInt(m["hr"]),
      spo2: asInt(m["spo2"]),
      lat: asDouble(m["lat"]),
      lng: asDouble(m["lng"]),
      ts: asInt(m["ts"]),
      status: (m["status"] ?? "FALL_CONFIRMED").toString(),
    );
  }
}
