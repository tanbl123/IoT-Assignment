import "package:flutter/material.dart";
import "package:intl/intl.dart";

import "../models/vitals.dart";
import "../services/database_service.dart";

/// Live status: current heart rate / SpO2, connection freshness, and a big red
/// banner when a fall alert is active.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final db = DatabaseService();
    return Scaffold(
      appBar: AppBar(title: const Text("Live Status")),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ---- Alert banner ----
          StreamBuilder<bool>(
            stream: db.alertActive(),
            builder: (context, snap) {
              if (snap.data != true) return const SizedBox.shrink();
              return Card(
                color: Colors.red.shade600,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded,
                          color: Colors.white, size: 36),
                      const SizedBox(width: 12),
                      const Expanded(
                        child: Text(
                          "FALL DETECTED",
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      FilledButton.tonal(
                        onPressed: db.clearAlert,
                        child: const Text("Acknowledge"),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),

          // ---- Live vitals ----
          StreamBuilder<Vitals?>(
            stream: db.latestVitals(),
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const Padding(
                  padding: EdgeInsets.all(32),
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              final v = snap.data;
              if (v == null) {
                return const Card(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Text(
                      "Waiting for the first reading from the backend…\n"
                      "Run live_inference.py (or the demo) to start streaming.",
                    ),
                  ),
                );
              }
              return Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _VitalTile(
                          label: "Heart Rate",
                          value: v.hr >= 0 ? "${v.hr}" : "--",
                          unit: "bpm",
                          icon: Icons.favorite,
                          color: Colors.red,
                        ),
                      ),
                      Expanded(
                        child: _VitalTile(
                          label: "SpO2",
                          value: v.spo2 >= 0 ? "${v.spo2}" : "--",
                          unit: "%",
                          icon: Icons.bloodtype,
                          color: Colors.blue,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.access_time),
                      title: Text("Status: ${v.status}"),
                      subtitle: Text(
                        "Updated ${DateFormat.yMMMd().add_jms().format(v.time)}",
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _VitalTile extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final Color color;

  const _VitalTile({
    required this.label,
    required this.value,
    required this.unit,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 8),
            Text(label, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            RichText(
              text: TextSpan(
                style: Theme.of(context).textTheme.headlineMedium,
                children: [
                  TextSpan(text: value),
                  TextSpan(
                    text: " $unit",
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
