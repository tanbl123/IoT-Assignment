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

// TODO: replace with YOUR Realtime Database URL.
const String kDatabaseUrl =
    "https://YOUR-PROJECT-default-rtdb.firebaseio.com";
