import "package:flutter/material.dart";
import "package:intl/intl.dart";
import "package:url_launcher/url_launcher.dart";

import "../models/vitals.dart";
import "../services/database_service.dart";
import "../widgets/location_view.dart";

/// "Where was the person?" — a timeline of places, newest first.
///
/// Every reading in all_records carries a GPS position. Listing them all would
/// be thousands of near-identical rows, so we collapse consecutive readings at
/// the same spot into one segment with a time range ("was here from X to Y").
class LocationHistoryScreen extends StatelessWidget {
  const LocationHistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final db = DatabaseService();
    return Scaffold(
      appBar: AppBar(title: const Text("Location History")),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: StreamBuilder<List<Vitals>>(
            stream: db.vitalsHistory(limit: 500),
            builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final segments = _segments(snap.data ?? []);
          if (segments.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  "No places recorded yet.\n"
                  "Locations will appear here once the device has a GPS signal.",
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            itemCount: segments.length,
            itemBuilder: (context, i) {
              final s = segments[i];
              return Card(
                elevation: 0,
                color: Colors.teal.withOpacity(0.07),
                margin: const EdgeInsets.only(bottom: 8),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
                child: ListTile(
                  leading: const CircleAvatar(
                    backgroundColor: Colors.teal,
                    child: Icon(Icons.place, color: Colors.white),
                  ),
                  title: LocationView(lat: s.lat, lng: s.lng),
                  subtitle: Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(_range(s.start, s.end)),
                  ),
                  isThreeLine: true,
                  trailing: IconButton(
                    icon: const Icon(Icons.map),
                    tooltip: "Open in Google Maps",
                    onPressed: () => launchUrl(
                      Uri.parse(
                        "https://www.google.com/maps/search/?api=1&query=${s.lat},${s.lng}",
                      ),
                      mode: LaunchMode.externalApplication,
                    ),
                  ),
                ),
              );
            },
          );
            },
          ),
        ),
      ),
    );
  }

  /// Group consecutive same-location readings (oldest->newest) into segments,
  /// then return them newest-first.
  static List<_Segment> _segments(List<Vitals> data) {
    final out = <_Segment>[];
    for (final v in data) {
      if (!v.hasGps) continue;
      final key =
          "${v.lat.toStringAsFixed(4)},${v.lng.toStringAsFixed(4)}";
      if (out.isNotEmpty && out.last.key == key) {
        out.last.end = v.time; // extend the current stay
      } else {
        out.add(_Segment(
          key: key,
          lat: v.lat,
          lng: v.lng,
          start: v.time,
          end: v.time,
        ));
      }
    }
    return out.reversed.toList(); // newest first
  }

  static String _range(DateTime start, DateTime end) {
    final day = DateFormat.yMMMEd();
    final t = DateFormat.jm();
    if (start == end) return "${day.format(start)} · ${t.format(start)}";
    final sameDay = start.year == end.year &&
        start.month == end.month &&
        start.day == end.day;
    if (sameDay) {
      return "${day.format(start)} · ${t.format(start)} – ${t.format(end)}";
    }
    return "${day.format(start)} ${t.format(start)} – "
        "${day.format(end)} ${t.format(end)}";
  }
}

class _Segment {
  final String key;
  final double lat;
  final double lng;
  final DateTime start;
  DateTime end;
  _Segment({
    required this.key,
    required this.lat,
    required this.lng,
    required this.start,
    required this.end,
  });
}
