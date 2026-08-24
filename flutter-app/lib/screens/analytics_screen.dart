import "package:flutter/material.dart";
import "package:fl_chart/fl_chart.dart";
import "package:intl/intl.dart";

import "../models/vitals.dart";
import "../models/fall_event.dart";
import "../services/database_service.dart";

/// Reports / analytics: the "Generate an analysis report from the collected
/// data" deliverable. Reads the append-only history the backend logs and turns
/// it into summary numbers + charts. A date picker lets a caregiver view a
/// specific day; by default it shows the most recent data.
class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  final DatabaseService _db = DatabaseService();
  DateTime? _selectedDay; // null = recent data (default)

  bool get _selectedIsToday {
    final d = _selectedDay;
    if (d == null) return false;
    final now = DateTime.now();
    return d.year == now.year && d.month == now.month && d.day == now.day;
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDay ?? now,
      firstDate: DateTime(2024),
      lastDate: now,
    );
    if (picked != null) setState(() => _selectedDay = picked);
  }

  List<Vitals> _filterByDay(List<Vitals> data) {
    final d = _selectedDay;
    if (d == null) return data;
    return data.where((v) {
      final t = v.time;
      return t.year == d.year && t.month == d.month && t.day == d.day;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Reports & Analytics")),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
          // ---------- Date selector ----------
          Card(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
              child: Row(
                children: [
                  const Icon(Icons.calendar_today, size: 20),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _selectedDay == null
                          ? "Showing: recent data"
                          : "Showing: ${DateFormat.yMMMEd().format(_selectedDay!)}",
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ),
                  if (_selectedDay != null && !_selectedIsToday)
                    TextButton(
                      onPressed: () => setState(() => _selectedDay = null),
                      child: const Text("Recent"),
                    ),
                  FilledButton.tonal(
                    onPressed: _pickDate,
                    child: const Text("Pick a date"),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // ---------- Vitals section ----------
          StreamBuilder<List<Vitals>>(
            stream: _db.vitalsHistory(limit: 2000),
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const _Loading();
              }
              final data = _filterByDay(snap.data ?? []);
              if (data.isEmpty) {
                return _EmptyCard(
                  _selectedDay == null
                      ? "No health data yet.\n"
                          "Charts will appear here once the device starts recording readings."
                      : "No readings recorded on "
                          "${DateFormat.yMMMEd().format(_selectedDay!)}.",
                );
              }
              final avgHr = _avg(data.map((v) => v.hr));
              final avgSpo2 = _avg(data.map((v) => v.spo2));
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _StatCard(
                        label: "Avg HR",
                        value: avgHr == null ? "--" : "${avgHr.round()}",
                        unit: "bpm",
                      ),
                      _StatCard(
                        label: "Avg SpO2",
                        value: avgSpo2 == null ? "--" : "${avgSpo2.round()}",
                        unit: "%",
                      ),
                      _StatCard(
                        label: "Readings",
                        value: "${data.length}",
                        unit: "",
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _SectionTitle("Heart rate over time"),
                  _LineCard(
                    spots: _spots(data, (v) => v.hr.toDouble()),
                    color: Colors.red,
                    hardMin: 0,
                  ),
                  const SizedBox(height: 16),
                  _SectionTitle("SpO2 over time"),
                  _LineCard(
                    spots: _spots(data, (v) => v.spo2.toDouble()),
                    color: Colors.blue,
                    hardMin: 0,
                    hardMax: 100, // SpO2 can't exceed 100%
                  ),
                  const SizedBox(height: 16),
                  _SectionTitle("Acceleration (motion) over time"),
                  _LineCard(
                    spots: _spots(data, (v) => v.accelG),
                    color: Colors.orange,
                    hardMin: 0,
                  ),
                ],
              );
            },
          ),

          const SizedBox(height: 24),

          // ---------- Falls section ----------
          StreamBuilder<List<FallEvent>>(
            stream: _db.falls(),
            builder: (context, snap) {
              final falls = snap.data ?? [];
              final perDay = _fallsPerDay(falls, days: 7);
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _StatCard(
                        label: "Total falls",
                        value: "${falls.length}",
                        unit: "",
                      ),
                      _StatCard(
                        label: "Last 7 days",
                        value: "${perDay.values.fold<int>(0, (a, b) => a + b)}",
                        unit: "",
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _SectionTitle("Falls per day (last 7 days)"),
                  _BarCard(perDay: perDay),
                ],
              );
            },
          ),
            ],
          ),
        ),
      ),
    );
  }

  // ---- helpers ----

  static double? _avg(Iterable<int> xs) {
    final valid = xs.where((x) => x >= 0).toList();
    if (valid.isEmpty) return null;
    return valid.reduce((a, b) => a + b) / valid.length;
  }

  static List<FlSpot> _spots(List<Vitals> data, double Function(Vitals) y) {
    final spots = <FlSpot>[];
    for (var i = 0; i < data.length; i++) {
      final val = y(data[i]);
      if (val >= 0) spots.add(FlSpot(i.toDouble(), val));
    }
    return spots;
  }

  /// Map of "MM/dd" -> fall count for the last [days] days (including empties).
  static Map<String, int> _fallsPerDay(List<FallEvent> falls, {int days = 7}) {
    final fmt = DateFormat("MM/dd");
    final now = DateTime.now();
    final out = <String, int>{};
    for (var d = days - 1; d >= 0; d--) {
      out[fmt.format(now.subtract(Duration(days: d)))] = 0;
    }
    for (final f in falls) {
      final key = fmt.format(f.time);
      if (out.containsKey(key)) out[key] = out[key]! + 1;
    }
    return out;
  }
}

// ===================== small reusable widgets =====================

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium),
      );
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  const _StatCard({required this.label, required this.value, required this.unit});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
          child: Column(
            children: [
              Text(value, style: Theme.of(context).textTheme.headlineSmall),
              if (unit.isNotEmpty)
                Text(unit, style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 4),
              Text(label,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.labelSmall),
            ],
          ),
        ),
      ),
    );
  }
}

class _LineCard extends StatelessWidget {
  final List<FlSpot> spots;
  final Color color;
  final double? hardMin; // never scale below this (e.g. 0)
  final double? hardMax; // never scale above this (e.g. 100 for SpO2)
  const _LineCard({
    required this.spots,
    required this.color,
    this.hardMin,
    this.hardMax,
  });

  /// Auto-fit the Y axis to the data (with padding) so spikes are never clipped.
  (double, double) _range() {
    if (spots.isEmpty) return (0, 1);
    var lo = spots.first.y, hi = spots.first.y;
    for (final s in spots) {
      if (s.y < lo) lo = s.y;
      if (s.y > hi) hi = s.y;
    }
    final span = hi - lo;
    final pad = span < 1 ? 5.0 : span * 0.15;
    lo -= pad;
    hi += pad;
    if (hardMin != null && lo < hardMin!) lo = hardMin!;
    if (hardMax != null && hi > hardMax!) hi = hardMax!;
    if (lo >= hi) hi = lo + 1; // guard against a flat/zero range
    return (lo, hi);
  }

  @override
  Widget build(BuildContext context) {
    final (minY, maxY) = _range();
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 16, 16, 8),
        child: SizedBox(
          height: 180,
          child: LineChart(
            LineChartData(
              minY: minY,
              maxY: maxY,
              gridData: const FlGridData(show: true),
              titlesData: const FlTitlesData(
                topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                rightTitles:
                    AxisTitles(sideTitles: SideTitles(showTitles: false)),
                bottomTitles:
                    AxisTitles(sideTitles: SideTitles(showTitles: false)),
              ),
              borderData: FlBorderData(show: false),
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  color: color,
                  barWidth: 2,
                  dotData: const FlDotData(show: false),
                  belowBarData: BarAreaData(
                    show: true,
                    color: color.withOpacity(0.12),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _BarCard extends StatelessWidget {
  final Map<String, int> perDay;
  const _BarCard({required this.perDay});

  @override
  Widget build(BuildContext context) {
    final labels = perDay.keys.toList();
    final maxCount = perDay.values.fold<int>(1, (a, b) => a > b ? a : b);
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 16, 16, 8),
        child: SizedBox(
          height: 200,
          child: BarChart(
            BarChartData(
              maxY: (maxCount + 1).toDouble(),
              gridData: const FlGridData(show: true),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                leftTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: true, reservedSize: 28),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 28,
                    getTitlesWidget: (value, meta) {
                      final i = value.toInt();
                      if (i < 0 || i >= labels.length) {
                        return const SizedBox.shrink();
                      }
                      return Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(labels[i],
                            style: const TextStyle(fontSize: 10)),
                      );
                    },
                  ),
                ),
              ),
              barGroups: [
                for (var i = 0; i < labels.length; i++)
                  BarChartGroupData(
                    x: i,
                    barRods: [
                      BarChartRodData(
                        toY: perDay[labels[i]]!.toDouble(),
                        color: Colors.deepOrange,
                        width: 16,
                        borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(4),
                        ),
                      ),
                    ],
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.all(32),
        child: Center(child: CircularProgressIndicator()),
      );
}

class _EmptyCard extends StatelessWidget {
  final String text;
  const _EmptyCard(this.text);
  @override
  Widget build(BuildContext context) => Card(
        child: Padding(padding: const EdgeInsets.all(24), child: Text(text)),
      );
}
