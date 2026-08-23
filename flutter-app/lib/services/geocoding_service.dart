import "dart:convert";

import "package:http/http.dart" as http;

/// Reverse geocoding: GPS coordinates -> human-readable place name.
///
/// Uses OpenStreetMap's Nominatim service — free, no API key, no billing.
/// Results are cached per rounded coordinate so we don't call the service on
/// every widget rebuild (and stay within its ~1 request/second fair-use rule).
class GeocodingService {
  static final Map<String, String> _cache = {};

  /// Returns a place name for [lat],[lng], or null if it can't be resolved.
  static Future<String?> reverseGeocode(double lat, double lng) async {
    // 0,0 is "Null Island" — treat as no fix.
    if (lat == 0 && lng == 0) return null;

    final key = "${lat.toStringAsFixed(4)},${lng.toStringAsFixed(4)}";
    if (_cache.containsKey(key)) return _cache[key];

    final url = Uri.parse(
      "https://nominatim.openstreetmap.org/reverse"
      "?format=jsonv2&lat=$lat&lon=$lng&zoom=18&addressdetails=1",
    );

    try {
      final res = await http.get(
        url,
        // Nominatim asks every app to identify itself.
        headers: {"User-Agent": "FallDetectionApp/1.0 (student project)"},
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final name = data["display_name"] as String?;
        if (name != null && name.isNotEmpty) {
          _cache[key] = name;
          return name;
        }
      }
    } catch (_) {
      // network/CORS/parse error -> fall back to coordinates only
    }
    return null;
  }
}
