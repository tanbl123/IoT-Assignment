/// One confirmed fall, matching the Firebase shape written by the backend:
///   fall_events/<pushId> : { hr, spo2, lat, lng, ts, status, accel_g }
class FallEvent {
  final String id; // Firebase push key
  final int hr;
  final int spo2;
  final double lat;
  final double lng;
  final int ts; // unix seconds
  final String status;
  final String image; // base64 data URI of the fall snapshot, or "" if none
  final double accelG; // peak impact G-force at the fall; -1 if not recorded
  final double tilt; // body tilt at the fall; -1 if not recorded
  final Map<String, dynamic> raw; // every field stored on the record

  const FallEvent({
    required this.id,
    required this.hr,
    required this.spo2,
    required this.lat,
    required this.lng,
    required this.ts,
    required this.status,
    this.image = "",
    this.accelG = -1,
    this.tilt = -1,
    this.raw = const {},
  });

  // ts may be seconds (10 digits, from the Python backend) or milliseconds
  // (13 digits, from older writers). Normalise both to a real DateTime.
  bool get hasGps => lat != 0.0 || lng != 0.0;
  bool get hasImage => image.isNotEmpty;
  bool get hasAccel => accelG >= 0;
  bool get hasTilt => tilt >= 0;

  DateTime get time => DateTime.fromMillisecondsSinceEpoch(
        ts > 1000000000000 ? ts : ts * 1000,
      );

  factory FallEvent.fromMap(String id, Map<dynamic, dynamic> m) {
    int asInt(dynamic v) =>
        v is int ? v : (v is double ? v.round() : int.tryParse("$v") ?? -1);
    double asDouble(dynamic v) =>
        v is double ? v : (v is int ? v.toDouble() : double.tryParse("$v") ?? 0.0);
    double asMeasure(dynamic v) =>
        v == null ? -1 : (v is num ? v.toDouble() : double.tryParse("$v") ?? -1);
    return FallEvent(
      id: id,
      hr: asInt(m["hr"]),
      spo2: asInt(m["spo2"]),
      lat: asDouble(m["lat"]),
      lng: asDouble(m["lng"]),
      ts: asInt(m["ts"]),
      status: (m["status"] ?? "FALL_CONFIRMED").toString(),
      image: (m["image"] ?? "").toString(),
      accelG: asMeasure(m["accel_g"]),
      tilt: asMeasure(m["tilt"]),
      raw: m.map((k, v) => MapEntry(k.toString(), v)),
    );
  }
}
