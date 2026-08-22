/// App configuration.
///
/// The Realtime Database URL is the ONLY value you must fill in by hand — it
/// tells the app which database the Python backend is writing to. Everything
/// else comes from `flutterfire configure` (see flutter-app/README.md).
///
/// Find this URL in the Firebase console:
///   Build -> Realtime Database -> the URL shown at the top, e.g.
///   https://smart-fall-detection-default-rtdb.firebaseio.com
///
/// It must match FIREBASE_DB_URL used by backend-python/firebase_client.py.
library;

// Realtime Database URL for the fall-detection-ed1a9 project.
// NOTE: this project lives in the asia-southeast1 region, so the URL ends in
// .asia-southeast1.firebasedatabase.app (NOT the default .firebaseio.com).
const String kDatabaseUrl =
    "https://fall-detection-ed1a9-default-rtdb.asia-southeast1.firebasedatabase.app";
