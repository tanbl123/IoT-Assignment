import "dart:async";

import "package:firebase_core/firebase_core.dart";
import "package:firebase_database/firebase_database.dart";

import "../config.dart";
import "../models/vitals.dart";
import "../models/fall_event.dart";

/// Thin wrapper over the Realtime Database. All screens read through here so the
/// Firebase paths live in exactly one place and stay in sync with the backend
/// (see backend-python/firebase_client.py):
///
///   telemetry/latest         -> live tile        (overwritten each reading)
///   all_records/<pushId>     -> HR/SpO2 charts    (append-only history of every
///                               reading; record_type marks normal vs fall)
///   falls/<pushId> + fall_events/<pushId> -> confirmed-fall history (merged;
///                               falls = older data, fall_events = new)
///   state/alert              -> red "FALL!" banner
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
  /// Reads all_records (every logged reading — normal + fall); each row carries
  /// hr/spo2/ts regardless of record_type, so all of them plot fine.
  Stream<List<Vitals>> vitalsHistory({int limit = 200}) {
    return _db
        .ref("all_records")
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

  /// Confirmed falls, newest first — MERGED from two nodes:
  ///   * falls        (older test data written by earlier code)
  ///   * fall_events  (what the current backend writes)
  /// so both historical and new falls appear in one list.
  Stream<List<FallEvent>> falls({int limit = 100}) {
    var fromFalls = <FallEvent>[];
    var fromEvents = <FallEvent>[];
    StreamSubscription? sub1, sub2;
    late StreamController<List<FallEvent>> controller;

    void emit() {
      // Merge both nodes, then de-duplicate: the same fall is logged by the
      // Python backend (fall_events, with location/image) AND ~10 s later by
      // the ESP32 gateway (falls, minimal). Collapse entries within 20 s into
      // one, keeping the richer record.
      final all = [...fromFalls, ...fromEvents]
        ..sort((a, b) => a.time.compareTo(b.time)); // oldest first
      final deduped = <FallEvent>[];
      for (final f in all) {
        if (deduped.isNotEmpty &&
            f.time.difference(deduped.last.time).abs() <=
                const Duration(seconds: 20)) {
          deduped[deduped.length - 1] = _richer(deduped.last, f);
        } else {
          deduped.add(f);
        }
      }
      deduped.sort((a, b) => b.time.compareTo(a.time)); // newest first
      if (!controller.isClosed) controller.add(deduped);
    }

    // Broadcast + lazy start so repeated widget rebuilds can re-listen safely.
    controller = StreamController<List<FallEvent>>.broadcast(
      onListen: () {
        sub1 = _fallsFrom("falls", limit).listen((v) {
          fromFalls = v;
          emit();
        });
        sub2 = _fallsFrom("fall_events", limit).listen((v) {
          fromEvents = v;
          emit();
        });
      },
      onCancel: () {
        sub1?.cancel();
        sub2?.cancel();
      },
    );
    return controller.stream;
  }

  /// Of two duplicate fall records, keep the one with more information
  /// (location > image > valid vitals).
  static FallEvent _richer(FallEvent a, FallEvent b) {
    int score(FallEvent f) =>
        (f.hasGps ? 4 : 0) + (f.hasImage ? 2 : 0) + (f.hr >= 0 ? 1 : 0);
    return score(b) > score(a) ? b : a;
  }

  /// Read one fall node into a list of FallEvent.
  Stream<List<FallEvent>> _fallsFrom(String node, int limit) {
    return _db
        .ref(node)
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
