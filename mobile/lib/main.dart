import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/home_shell.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/login_screen.dart';

void main() {
  runApp(const ProviderScope(child: FoodGadApp()));
}

class FoodGadApp extends StatelessWidget {
  const FoodGadApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FoodGad',
      debugShowCheckedModeBanner: false,
      theme: foodGadTheme(),
      darkTheme: foodGadTheme(),
      themeMode: ThemeMode.light,
      home: const _AuthGate(),
    );
  }
}

// --- Warm editorial palette (matches the web + the mobile mockup) ----------
const kCream = Color(0xFFF4EFE6); // background
const kCard = Color(0xFFFBF8F2); // cards
const kTerracotta = Color(0xFFC2632F); // primary
const kInk = Color(0xFF2A2620); // text
const kMuted = Color(0xFF8A847A); // muted text
const kBorder = Color(0xFFE6DDCD); // borders
const kSecondary = Color(0xFFEFE7D8); // chips / table header
const kSidebar = Color(0xFF2A2422); // dark accents
const kGood = Color(0xFF5C7A4A); // green (down)
const kBad = Color(0xFFB23A2E); // red (up)
const kWarn = Color(0xFFB8763A); // amber

ThemeData foodGadTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: kTerracotta,
    brightness: Brightness.light,
  ).copyWith(
    primary: kTerracotta,
    onPrimary: Colors.white,
    secondary: kSecondary,
    onSecondary: kInk,
    surface: kCream,
    onSurface: kInk,
    error: kBad,
    outline: kBorder,
    outlineVariant: kBorder,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: kCream,
    cardColor: kCard,
    appBarTheme: const AppBarTheme(
      backgroundColor: kCream,
      foregroundColor: kInk,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: kTerracotta,
        foregroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: kCard,
      hintStyle: const TextStyle(color: kMuted, fontSize: 13),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(11),
        borderSide: const BorderSide(color: kBorder),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(11),
        borderSide: const BorderSide(color: kBorder),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(11),
        borderSide: const BorderSide(color: kTerracotta),
      ),
    ),
    dividerColor: kBorder,
  );
}

/// Serif headline style (mimics Newsreader); falls back to the platform serif.
const TextStyle kSerif = TextStyle(
  fontFamily: 'serif',
  fontWeight: FontWeight.w600,
  color: kInk,
);

/// Switches between the login screen and the app shell based on auth status.
class _AuthGate extends ConsumerWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(authControllerProvider).status;
    switch (status) {
      case AuthStatus.unknown:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.authenticated:
        return const HomeShell();
      case AuthStatus.unauthenticated:
        return const LoginScreen();
    }
  }
}
