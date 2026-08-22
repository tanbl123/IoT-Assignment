import "package:flutter/material.dart";
import "package:fl_chart/fl_chart.dart";
import "package:intl/intl.dart";

import "../models/vitals.dart";
import "../models/fall_event.dart";
import "../services/database_service.dart";

/// Reports / analytics: the "Generate an analysis report from the collected
/// data" deliverable. Reads the append-only history the backend logs and turns
/// it into summary numbers + charts.
class AnalyticsScreen extends StatelessWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final db = DatabaseService();
    return Scaffold(
      appBar: AppBar(title: const Text("Reports & Analytics")),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ---------- Vitals section ----------
          StreamBuilder<List<Vitals>>(
            stream: db.vitalsHistory(),
            builder: (context, snap) {
              final data = snap.data ?? [];
              if (snap.connectionState == ConnectionState.waiting) {
                return const _Loading();
              }
              if (data.isEmpty) {
                return const _EmptyCard(
                  "No vitals history yet.\nThe backend appends a reading to "
                  "all_records every few seconds once it is streaming.",
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
                    minY: 40,
                    maxY: 160,
                  ),
                  const SizedBox(height: 16),
                  _SectionTitle("SpO2 over time"),
                  _LineCard(
                    spots: _spots(data, (v) => v.spo2.toDouble()),
                    color: Colors.blue,
                    minY: 80,
                    maxY: 100,
                  ),
                ],
              );
            },
          ),

          const SizedBox(height: 24),

          // ---------- Falls section ----------
          StreamBuilder<List<FallEvent>>(
            stream: db.falls(),
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
  final double minY;
  final double maxY;
  const _LineCard({
    required this.spots,
    required this.color,
    required this.minY,
    required this.maxY,
  });

  @override
  Widget build(BuildContext context) {
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
