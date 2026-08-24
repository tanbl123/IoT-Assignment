import "package:flutter/material.dart";

import "../services/geocoding_service.dart";

/// Shows a GPS position as "Place name (longitude: x, latitude: y)".
///
/// Reverse-geocodes the coordinates (OpenStreetMap) and, while that loads or if
/// it fails, shows the coordinates alone. Stateful so the lookup only re-runs
/// when the coordinates actually change — not on every parent rebuild (which
/// would make it flicker "Locating…").
class LocationView extends StatefulWidget {
  final double lat;
  final double lng;
  final TextStyle? style;
  const LocationView({
    super.key,
    required this.lat,
    required this.lng,
    this.style,
  });

  @override
  State<LocationView> createState() => _LocationViewState();
}

class _LocationViewState extends State<LocationView> {
  late Future<String?> _future;

  @override
  void initState() {
    super.initState();
    _future = GeocodingService.reverseGeocode(widget.lat, widget.lng);
  }

  @override
  void didUpdateWidget(LocationView old) {
    super.didUpdateWidget(old);
    if (old.lat != widget.lat || old.lng != widget.lng) {
      _future = GeocodingService.reverseGeocode(widget.lat, widget.lng);
    }
  }

  String get _coords =>
      "(longitude: ${widget.lng.toStringAsFixed(5)}, latitude: ${widget.lat.toStringAsFixed(5)})";

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String?>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return Text("Locating…  $_coords", style: widget.style);
        }
        final name = snap.data;
        return Text(
          name != null ? "$name\n$_coords" : _coords,
          style: widget.style,
        );
      },
    );
  }
}
