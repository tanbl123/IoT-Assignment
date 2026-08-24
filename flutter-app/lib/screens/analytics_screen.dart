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
  String _mode = "all"; // all | 15m | 1h | 6h | date
  DateTime? _selectedDay; // used when _mode == "date"

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDay ?? now,
      firstDate: DateTime(2024),
      lastDate: now,
    );
    if (picked != null) {
      setState(() {
        _selectedDay = picked;
        _mode = "date";
      });
    }
  }

  /// Filter readings by the selected window (relative to now) or a specific day.
  List<Vitals> _filter(List<Vitals> data) {
    final now = DateTime.now();
    switch (_mode) {
      case "15m":
        return data
            .where((v) => now.difference(v.time) <= const Duration(minutes: 15))
            .toList();
      case "1h":
        return data
            .where((v) => now.difference(v.time) <= const Duration(hours: 1))
            .toList();
      case "6h":
        return data
            .where((v) => now.difference(v.time) <= const Duration(hours: 6))
            .toList();
      case "date":
        final d = _selectedDay;
        if (d == null) return data;
        return data.where((v) {
          final t = v.time;
          return t.year == d.year && t.month == d.month && t.day == d.day;
        }).toList();
      default:
        return data;
    }
  }

  String get _emptyMsg {
    switch (_mode) {
      case "15m":
        return "No readings in the last 15 minutes.";
      case "1h":
        return "No readings in the last hour.";
      case "6h":
        return "No readings in the last 6 hours.";
      case "date":
        return _selectedDay == null
            ? "No readings for the selected day."
            : "No readings recorded on "
                "${DateFormat.yMMMEd().format(_selectedDay!)}.";
      default:
        return "No health data yet.\n"
            "Charts will appear here once the device starts recording readings.";
    }
  }

  Widget _rangeBar() {
    Widget chip(String label, String mode) => Padding(
          padding: const EdgeInsets.only(right: 8),
          child: ChoiceChip(
            label: Text(label),
            selected: _mode == mode,
            onSelected: (_) => setState(() => _mode = mode),
          ),
        );
    final dateLabel = _mode == "date" && _selectedDay != null
        ? DateFormat.MMMd().format(_selectedDay!)
        : "Pick a date";
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          chip("All", "all"),
          chip("15 min", "15m"),
          chip("1 hour", "1h"),
          chip("6 hours", "6h"),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              avatar: const Icon(Icons.calendar_today, size: 16),
              label: Text(dateLabel),
              selected: _mode == "date",
              onSelected: (_) => _pickDate(),
            ),
          ),
        ],
      ),
    );
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
          // ---------- Time range selector ----------
          _rangeBar(),
          const SizedBox(height: 12),

          // ---------- Vitals section ----------
          StreamBuilder<List<Vitals>>(
            stream: _db.vitalsHistory(limit: 2000),
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const _Loading();
              }
              final data = _filter(snap.data ?? []);
              if (data.isEmpty) {
                return _EmptyCard(_emptyMsg);
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

  /// Plot each reading at its real time on the x-axis (milliseconds since
  /// epoch) so gaps and bursts are shown accurately — not evenly by count.
  static List<FlSpot> _spots(List<Vitals> data, double Function(Vitals) y) {
    final spots = <FlSpot>[];
    for (final v in data) {
      final val = y(v);
      if (val >= 0) {
        spots.add(FlSpot(v.time.millisecondsSinceEpoch.toDouble(), val));
      }
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
  final List<FlSpot> spots; // x = time in ms since epoch, y = value
  final Color color;
  final double? hardMin; // never scale below this (e.g. 0)
  final double? hardMax; // never scale above this (e.g. 100 for SpO2)
  const _LineCard({
    required this.spots,
    required this.color,
    this.hardMin,
    this.hardMax,
  });

  /// A "nice" step size for the axis given the data span.
  static double _niceStep(double span) {
    if (span <= 10) return 2;
    if (span <= 25) return 5;
    if (span <= 60) return 10;
    if (span <= 150) return 25;
    if (span <= 300) return 50;
    return 100;
  }

  /// A "nice" time step (in ms) for the x-axis, so labels land on clean clock
  /// times (e.g. every 10 min: 12:00, 12:10, 12:20) — evenly spaced and never
  /// overlapping, because multiples of a minute-step align to real clock times.
  static double _niceTimeStepMs(double spanMs) {
    final min = spanMs / 60000.0; // span in minutes
    double stepMin;
    if (min <= 4) {
      stepMin = 1;
    } else if (min <= 12) {
      stepMin = 2;
    } else if (min <= 30) {
      stepMin = 5;
    } else if (min <= 70) {
      stepMin = 10;
    } else if (min <= 150) {
      stepMin = 30;
    } else if (min <= 400) {
      stepMin = 60;
    } else {
      stepMin = 180;
    }
    return stepMin * 60000.0;
  }

  /// Auto-fit the Y axis to the data, rounded to clean numbers so the axis
  /// labels are tidy (e.g. 50, 75, 100 — not 49.56, 235.4). Returns
  /// (minY, maxY, interval).
  (double, double, double) _range() {
    if (spots.isEmpty) return (0, 1, 1);
    var lo = spots.first.y, hi = spots.first.y;
    for (final s in spots) {
      if (s.y < lo) lo = s.y;
      if (s.y > hi) hi = s.y;
    }
    final step = _niceStep(hi - lo);
    lo = (lo / step).floorToDouble() * step;
    hi = (hi / step).ceilToDouble() * step;
    if (hardMin != null && lo < hardMin!) lo = hardMin!;
    if (hardMax != null && hi > hardMax!) hi = hardMax!;
    if (lo >= hi) hi = lo + step; // guard against a flat/zero range
    return (lo, hi, step);
  }

  /// Split the points into separate line segments wherever there's a time gap
  /// bigger than [gapMs] (the device was off) — so we don't draw a misleading
  /// straight line across a period when nothing was recorded.
  List<List<FlSpot>> _segments({double gapMs = 60000}) {
    final segs = <List<FlSpot>>[];
    var cur = <FlSpot>[];
    for (final s in spots) {
      if (cur.isNotEmpty && s.x - cur.last.x > gapMs) {
        segs.add(cur);
        cur = [];
      }
      cur.add(s);
    }
    if (cur.isNotEmpty) segs.add(cur);
    return segs;
  }

  @override
  Widget build(BuildContext context) {
    final (minY, maxY, interval) = _range();
    // X axis = time (ms since epoch).
    var minX = spots.isEmpty ? 0.0 : spots.first.x;
    var maxX = spots.isEmpty ? 1.0 : spots.first.x;
    for (final s in spots) {
      if (s.x < minX) minX = s.x;
      if (s.x > maxX) maxX = s.x;
    }
    final xSpan = maxX - minX;
    final xInterval = xSpan <= 0 ? 60000.0 : _niceTimeStepMs(xSpan);
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 16, 16, 8),
        child: SizedBox(
          height: 180,
          child: LineChart(
            LineChartData(
              minX: minX,
              maxX: maxX,
              minY: minY,
              maxY: maxY,
              gridData: FlGridData(
                show: true,
                horizontalInterval: interval,
                verticalInterval: xInterval,
              ),
              titlesData: FlTitlesData(
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: spots.length > 1,
                    reservedSize: 26,
                    interval: xInterval,
                    // don't force labels at the exact data start/end — they
                    // collide with the clean interval labels next to them.
                    minIncluded: false,
                    maxIncluded: false,
                    getTitlesWidget: (value, meta) {
                      final dt = DateTime.fromMillisecondsSinceEpoch(
                        value.toInt(),
                      );
                      return Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          DateFormat.jm().format(dt),
                          style: const TextStyle(fontSize: 9),
                        ),
                      );
                    },
                  ),
                ),
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    interval: interval,
                    reservedSize: 40,
                    getTitlesWidget: (value, meta) => Padding(
                      padding: const EdgeInsets.only(right: 4),
                      child: Text(
                        value.toStringAsFixed(0),
                        style: const TextStyle(fontSize: 10),
                      ),
                    ),
                  ),
                ),
              ),
              borderData: FlBorderData(show: false),
              lineBarsData: [
                // one line per continuous run — gaps (device off) are not joined
                for (final seg in _segments())
                  LineChartBarData(
                    spots: seg,
                    isCurved: false,
                    color: color,
                    barWidth: 2,
                    dotData: FlDotData(
                      // show a dot for an isolated single reading so it's visible
                      show: seg.length == 1,
                    ),
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
    // Clean whole-number Y scale with a bit of headroom above the tallest bar.
    final step = maxCount <= 4
        ? 1.0
        : maxCount <= 10
            ? 2.0
            : maxCount <= 25
                ? 5.0
                : 10.0;
    final maxY = ((maxCount / step).floor() + 1) * step;
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 16, 16, 8),
        child: SizedBox(
          height: 200,
          child: BarChart(
            BarChartData(
              maxY: maxY,
              gridData: FlGridData(show: true, horizontalInterval: step),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 28,
                    interval: step,
                    getTitlesWidget: (value, meta) => Text(
                      value.toInt().toString(),
                      style: const TextStyle(fontSize: 10),
                    ),
                  ),
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
