// PLACEHOLDER — replace by running `flutterfire configure` (see README).
//
// `flutterfire configure` connects this app to your Firebase project and
// OVERWRITES this file with the real API keys / app IDs for each platform.
// Until you run it, the app will stop at startup with the message below
// instead of crashing with a confusing error.
//
// These values are client config, not secrets, but google-services.json /
// GoogleService-Info.plist are gitignored per the project rules — so each
// teammate runs `flutterfire configure` once on their own machine.

import "package:firebase_core/firebase_core.dart";

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    throw UnsupportedError(
      "firebase_options.dart is still the placeholder.\n"
      "Run:  flutterfire configure\n"
      "from the flutter-app/ folder to generate the real one, then rebuild.",
    );
  }
}
