import "package:flutter/material.dart";
import "package:firebase_core/firebase_core.dart";

import "firebase_options.dart";
import "screens/home_screen.dart";
import "screens/history_screen.dart";
import "screens/analytics_screen.dart";

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const FallApp());
}

class FallApp extends StatelessWidget {
  const FallApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "Fall Detection",
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: Colors.teal,
        useMaterial3: true,
      ),
      home: const RootNav(),
    );
  }
}

/// Bottom-navigation shell: Live status / Fall history / Analytics report.
class RootNav extends StatefulWidget {
  const RootNav({super.key});

  @override
  State<RootNav> createState() => _RootNavState();
}

class _RootNavState extends State<RootNav> {
  int _index = 0;

  static const _screens = [
    HomeScreen(),
    HistoryScreen(),
    AnalyticsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.favorite_border),
            selectedIcon: Icon(Icons.favorite),
            label: "Live",
          ),
          NavigationDestination(
            icon: Icon(Icons.history),
            label: "Falls",
          ),
          NavigationDestination(
            icon: Icon(Icons.insights),
            label: "Reports",
          ),
        ],
      ),
    );
  }
}
