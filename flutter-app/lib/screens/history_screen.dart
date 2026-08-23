import "package:flutter/material.dart";
import "package:intl/intl.dart";

import "../models/fall_event.dart";
import "../services/database_service.dart";
import "../widgets/location_view.dart";
import "fall_detail_screen.dart";

/// Scrollable log of every confirmed fall (Firebase `falls/`), newest first.
class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final db = DatabaseService();
    return Scaffold(
      appBar: AppBar(title: const Text("Fall History")),
      body: StreamBuilder<List<FallEvent>>(
        stream: db.falls(),
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final falls = snap.data ?? [];
          if (falls.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  "No falls recorded — that's good news! 🎉",
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }
          return ListView.separated(
            itemCount: falls.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final f = falls[i];
              return ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Colors.red,
                  child: Icon(Icons.personal_injury, color: Colors.white),
                ),
                title: Text(
                  DateFormat.yMMMEd().add_jms().format(f.time),
                ),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "HR ${f.hr >= 0 ? f.hr : '--'} bpm   •   "
                      "SpO2 ${f.spo2 >= 0 ? f.spo2 : '--'}%",
                    ),
                    if (f.hasGps)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: LocationView(
                          lat: f.lat,
                          lng: f.lng,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                  ],
                ),
                isThreeLine: f.hasGps,
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => FallDetailScreen(fall: f),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
