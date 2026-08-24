import "package:flutter/material.dart";
import "package:intl/intl.dart";

import "../models/fall_event.dart";
import "../services/database_service.dart";
import "../widgets/location_view.dart";
import "fall_detail_screen.dart";

/// Log of confirmed falls (merged `falls` + `fall_events`), newest first, with
/// a date-range filter. Falls are rare events, so a range (last 7/30 days or a
/// custom range) is more useful than a single-day picker.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final DatabaseService _db = DatabaseService();
  String _mode = "all"; // all | 7d | 30d | custom
  DateTimeRange? _customRange;

  DateTimeRange? get _range {
    final now = DateTime.now();
    switch (_mode) {
      case "7d":
        return DateTimeRange(
            start: now.subtract(const Duration(days: 6)), end: now);
      case "30d":
        return DateTimeRange(
            start: now.subtract(const Duration(days: 29)), end: now);
      case "custom":
        return _customRange;
      default:
        return null; // all
    }
  }

  bool _inRange(DateTime t) {
    final r = _range;
    if (r == null) return true;
    final start = DateTime(r.start.year, r.start.month, r.start.day);
    final end = DateTime(r.end.year, r.end.month, r.end.day, 23, 59, 59);
    return !t.isBefore(start) && !t.isAfter(end);
  }

  Future<void> _pickCustomRange() async {
    final now = DateTime.now();
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2024),
      lastDate: now,
      initialDateRange: _customRange,
    );
    if (picked != null) {
      setState(() {
        _customRange = picked;
        _mode = "custom";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Fall History")),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: Column(
            children: [
              _filterBar(),
              Expanded(
                child: StreamBuilder<List<FallEvent>>(
                  stream: _db.falls(),
                  builder: (context, snap) {
                    if (snap.connectionState == ConnectionState.waiting) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    final falls = (snap.data ?? [])
                        .where((f) => _inRange(f.time))
                        .toList();
                    if (falls.isEmpty) {
                      return Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Text(
                            _mode == "all"
                                ? "No falls recorded — that's good news! 🎉"
                                : "No falls in the selected period. 🎉",
                            textAlign: TextAlign.center,
                          ),
                        ),
                      );
                    }
                    return ListView.builder(
                      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                      itemCount: falls.length + 1,
                      itemBuilder: (context, i) {
                        if (i == 0) {
                          return Padding(
                            padding: const EdgeInsets.fromLTRB(4, 4, 4, 8),
                            child: Text(
                              "${falls.length} fall${falls.length == 1 ? '' : 's'}"
                              "${_mode == 'all' ? '' : ' in this period'}",
                              style: Theme.of(context).textTheme.titleSmall
                                  ?.copyWith(color: Colors.grey.shade600),
                            ),
                          );
                        }
                        return _fallTile(falls[i - 1]);
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _filterBar() {
    Widget chip(String label, String mode) => Padding(
          padding: const EdgeInsets.only(right: 8),
          child: ChoiceChip(
            label: Text(label),
            selected: _mode == mode,
            onSelected: (_) => setState(() => _mode = mode),
          ),
        );

    final customLabel = _mode == "custom" && _customRange != null
        ? "${DateFormat.MMMd().format(_customRange!.start)} – "
            "${DateFormat.MMMd().format(_customRange!.end)}"
        : "Custom";

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          chip("All", "all"),
          chip("Last 7 days", "7d"),
          chip("Last 30 days", "30d"),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              avatar: const Icon(Icons.date_range, size: 18),
              label: Text(customLabel),
              selected: _mode == "custom",
              onSelected: (_) => _pickCustomRange(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _fallTile(FallEvent f) {
    return Card(
      elevation: 0,
      color: Colors.red.withOpacity(0.06),
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: ListTile(
        leading: const CircleAvatar(
          backgroundColor: Colors.red,
          child: Icon(Icons.personal_injury, color: Colors.white),
        ),
      title: Text(DateFormat.yMMMEd().add_jms().format(f.time)),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            "HR ${f.hr >= 0 ? f.hr : '--'} bpm   •   "
            "SpO2 ${f.spo2 >= 0 ? f.spo2 : '--'}%"
            "${f.hasAccel ? '   •   Impact ${f.accelG.toStringAsFixed(1)} g' : ''}",
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
        MaterialPageRoute(builder: (_) => FallDetailScreen(fall: f)),
      ),
      ),
    );
  }
}
