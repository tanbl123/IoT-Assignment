import "package:flutter/material.dart";
import "package:intl/intl.dart";

import "../models/vitals.dart";
import "../services/database_service.dart";
import "../widgets/location_view.dart";

/// Live status: a status hero, the current vitals/motion tiles, and location.
/// A big red banner replaces the hero when a fall alert is active.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final db = DatabaseService();
    return Scaffold(
      appBar: AppBar(title: const Text("Live Status")),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: StreamBuilder<Vitals?>(
            stream: db.latestVitals(),
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              final v = snap.data;
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // ---- status hero / alert banner ----
                  StreamBuilder<bool>(
                    stream: db.alertActive(),
                    builder: (context, alertSnap) {
                      final alerting = alertSnap.data == true;
                      return _StatusHero(
                        vitals: v,
                        alerting: alerting,
                        onAcknowledge: db.clearAlert,
                      );
                    },
                  ),
                  const SizedBox(height: 16),

                  if (v == null)
                    const Card(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                          "Connecting to the device…\n"
                          "Live readings will appear here once the device is switched on.",
                        ),
                      ),
                    )
                  else ...[
                    // ---- vitals + motion tiles ----
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
                        const SizedBox(width: 12),
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
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: _VitalTile(
                            label: "Acceleration",
                            value: v.accelG >= 0
                                ? v.accelG.toStringAsFixed(2)
                                : "--",
                            unit: "g",
                            icon: Icons.speed,
                            color: Colors.orange,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _VitalTile(
                            label: "Tilt",
                            value:
                                v.tilt >= 0 ? v.tilt.toStringAsFixed(0) : "--",
                            unit: "°",
                            icon: Icons.screen_rotation,
                            color: Colors.purple,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // ---- location ----
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.location_on,
                                color: v.hasGps
                                    ? Colors.teal
                                    : Colors.grey.shade400),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text("Location",
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleSmall),
                                  const SizedBox(height: 4),
                                  v.hasGps
                                      ? LocationView(lat: v.lat, lng: v.lng)
                                      : const Text("Acquiring GPS signal…"),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Big banner at the top: green while normal, red while a fall alert is active.
class _StatusHero extends StatelessWidget {
  final Vitals? vitals;
  final bool alerting;
  final VoidCallback onAcknowledge;
  const _StatusHero({
    required this.vitals,
    required this.alerting,
    required this.onAcknowledge,
  });

  @override
  Widget build(BuildContext context) {
    if (alerting) {
      return _shell(
        colors: [Colors.red.shade400, Colors.red.shade700],
        icon: Icons.warning_amber_rounded,
        title: "FALL DETECTED",
        subtitle: "Tap acknowledge once you've checked on them",
        trailing: FilledButton.tonal(
          onPressed: onAcknowledge,
          child: const Text("Acknowledge"),
        ),
      );
    }

    final v = vitals;
    final connecting = v == null;
    final subtitle = connecting
        ? "Connecting to the device…"
        : (v.hasValidTime
            ? "Updated ${DateFormat.jm().format(v.time)}"
            : "Receiving live data");

    return _shell(
      colors: connecting
          ? [Colors.blueGrey.shade300, Colors.blueGrey.shade500]
          : [Colors.teal.shade400, Colors.teal.shade700],
      icon: connecting ? Icons.sync : Icons.shield_outlined,
      title: connecting ? "Connecting" : _friendlyStatus(v.status),
      subtitle: subtitle,
    );
  }

  Widget _shell({
    required List<Color> colors,
    required IconData icon,
    required String title,
    required String subtitle,
    Widget? trailing,
  }) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: colors,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(icon, color: Colors.white, size: 40),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                ),
              ],
            ),
          ),
          if (trailing != null) trailing,
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
      elevation: 0,
      color: color.withOpacity(0.08),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 12),
        child: Column(
          children: [
            CircleAvatar(
              radius: 24,
              backgroundColor: color.withOpacity(0.18),
              child: Icon(icon, color: color, size: 26),
            ),
            const SizedBox(height: 12),
            Text(
              label,
              style: Theme.of(context)
                  .textTheme
                  .labelMedium
                  ?.copyWith(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 6),
            RichText(
              text: TextSpan(
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).textTheme.headlineMedium?.color,
                    ),
                children: [
                  TextSpan(text: value),
                  TextSpan(
                    text: " $unit",
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: Colors.grey.shade600),
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

/// Turn a raw status string into something friendly for the caregiver.
String _friendlyStatus(String s) {
  final u = s.trim().toUpperCase();
  if (u.isEmpty || u == "UNKNOWN") return "Monitoring";
  if (u == "OK") return "Normal";
  if (u.contains("FALL")) return "Fall detected";
  return s;
}
