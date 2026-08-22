import "package:firebase_core/firebase_core.dart";
import "package:firebase_database/firebase_database.dart";

import "../config.dart";
import "../models/vitals.dart";
import "../models/fall_event.dart";

/// Thin wrapper over the Realtime Database. All screens read through here so the
/// Firebase paths live in exactly one place and stay in sync with the backend:
///
///   telemetry/latest        -> live tile          (overwritten each reading)
///   history/vitals/<pushId> -> HR/SpO2 charts     (append-only time-series)
///   falls/<pushId>          -> fall history + report counts
///   state/alert             -> red "FALL!" banner
class DatabaseService {
  DatabaseService() : _db = FirebaseDatabase.instanceFor(
          app: Firebase.app(),
          databaseURL: kDatabaseUrl,
        );

  final FirebaseDatabase _db;

  /// Newest single vitals reading (live tile). null until the backend writes.
  Stream<Vitals?> latestVitals() {
    return _db.ref("telemetry/latest").onValue.map((event) {
      final v = event.snapshot.value;
      if (v is Map) return Vitals.fromMap(v);
      return null;
    });
  }

  /// Time-series of vitals for the analytics charts, oldest -> newest.
  Stream<List<Vitals>> vitalsHistory({int limit = 200}) {
    return _db
        .ref("history/vitals")
        .orderByChild("ts")
        .limitToLast(limit)
        .onValue
        .map((event) {
      final out = <Vitals>[];
      final v = event.snapshot.value;
      if (v is Map) {
        v.forEach((_, value) {
          if (value is Map) out.add(Vitals.fromMap(value));
        });
      }
      out.sort((a, b) => a.ts.compareTo(b.ts));
      return out;
    });
  }

  /// Confirmed falls, newest first.
  Stream<List<FallEvent>> falls({int limit = 100}) {
    return _db
        .ref("falls")
        .orderByChild("ts")
        .limitToLast(limit)
        .onValue
        .map((event) {
      final out = <FallEvent>[];
      final v = event.snapshot.value;
      if (v is Map) {
        v.forEach((key, value) {
          if (value is Map) out.add(FallEvent.fromMap("$key", value));
        });
      }
      out.sort((a, b) => b.ts.compareTo(a.ts)); // newest first
      return out;
    });
  }

  /// Whether an alert is currently active (drives the red banner).
  Stream<bool> alertActive() {
    return _db.ref("state/alert").onValue.map(
          (event) => event.snapshot.value == true,
        );
  }

  /// Caregiver taps "Acknowledge" -> clear the alert flag.
  Future<void> clearAlert() async {
    await _db.ref("state/alert").set(false);
    await _db.ref("state/confirmed").set(false);
  }
}
