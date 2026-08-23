import "package:flutter/material.dart";
import "package:intl/intl.dart";
import "package:url_launcher/url_launcher.dart";

import "../models/fall_event.dart";
import "../widgets/location_view.dart";

/// Full detail for one confirmed fall — opened by tapping a row in the Falls
/// tab. Shows time, status, vitals, location (place name + map link) and every
/// field that was recorded for the event.
class FallDetailScreen extends StatelessWidget {
  final FallEvent fall;
  const FallDetailScreen({super.key, required this.fall});

  Future<void> _openMap() async {
    final uri = Uri.parse(
      "https://www.google.com/maps/search/?api=1&query=${fall.lat},${fall.lng}",
    );
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    // Keep the well-known fields out of the "all data" dump (shown above).
    const shown = {"hr", "spo2", "lat", "lng", "ts", "status"};
    final extra = fall.raw.entries.where((e) => !shown.contains(e.key)).toList();

    return Scaffold(
      appBar: AppBar(title: const Text("Fall Detail")),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ---- header ----
          Card(
            color: Colors.red.shade50,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const CircleAvatar(
                    radius: 26,
                    backgroundColor: Colors.red,
                    child: Icon(Icons.personal_injury,
                        color: Colors.white, size: 30),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(fall.status,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(color: Colors.red.shade700)),
                        const SizedBox(height: 4),
                        Text(DateFormat.yMMMMEEEEd().add_jms().format(fall.time)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),

          // ---- vitals ----
          Row(
            children: [
              Expanded(
                child: _InfoTile(
                  icon: Icons.favorite,
                  color: Colors.red,
                  label: "Heart Rate",
                  value: fall.hr >= 0 ? "${fall.hr} bpm" : "Not recorded",
                ),
              ),
              Expanded(
                child: _InfoTile(
                  icon: Icons.bloodtype,
                  color: Colors.blue,
                  label: "SpO2",
                  value: fall.spo2 >= 0 ? "${fall.spo2} %" : "Not recorded",
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // ---- location ----
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.location_on, color: Colors.teal),
                      const SizedBox(width: 8),
                      Text("Location",
                          style: Theme.of(context).textTheme.titleSmall),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (fall.hasGps) ...[
                    LocationView(lat: fall.lat, lng: fall.lng),
                    const SizedBox(height: 8),
                    FilledButton.tonalIcon(
                      onPressed: _openMap,
                      icon: const Icon(Icons.map),
                      label: const Text("Open in Google Maps"),
                    ),
                  ] else
                    const Text("No location was recorded for this fall."),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),

          // ---- all recorded fields ----
          if (extra.isNotEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text("Other recorded data",
                        style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 8),
                    for (final e in extra)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(
                              width: 140,
                              child: Text("${e.key}:",
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w600)),
                            ),
                            Expanded(child: Text("${e.value}")),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String label;
  final String value;
  const _InfoTile({
    required this.icon,
    required this.color,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 6),
            Text(label, style: Theme.of(context).textTheme.labelMedium),
            const SizedBox(height: 4),
            Text(value, style: Theme.of(context).textTheme.titleMedium),
          ],
        ),
      ),
    );
  }
}
