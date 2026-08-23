import "package:flutter/material.dart";

import "../services/geocoding_service.dart";

/// Shows a GPS position as "Place name (longitude: x, latitude: y)".
///
/// Reverse-geocodes the coordinates (OpenStreetMap) and, while that loads or if
/// it fails, shows the coordinates alone. Used on the Live tile and the Falls
/// list so location is displayed the same way everywhere.
class LocationView extends StatelessWidget {
  final double lat;
  final double lng;
  final TextStyle? style;
  const LocationView({
    super.key,
    required this.lat,
    required this.lng,
    this.style,
  });

  String get _coords =>
      "(longitude: ${lng.toStringAsFixed(5)}, latitude: ${lat.toStringAsFixed(5)})";

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String?>(
      future: GeocodingService.reverseGeocode(lat, lng),
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return Text("Locating…  $_coords", style: style);
        }
        final name = snap.data;
        return Text(name != null ? "$name\n$_coords" : _coords, style: style);
      },
    );
  }
}
