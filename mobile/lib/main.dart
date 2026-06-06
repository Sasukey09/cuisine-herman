import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/home_shell.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/login_screen.dart';

void main() {
  runApp(const ProviderScope(child: CuisineHermanApp()));
}

class CuisineHermanApp extends StatelessWidget {
  const CuisineHermanApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Cuisine Herman',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF16a34a),
        useMaterial3: true,
        brightness: Brightness.light,
      ),
      darkTheme: ThemeData(
        colorSchemeSeed: const Color(0xFF16a34a),
        useMaterial3: true,
        brightness: Brightness.dark,
      ),
      home: const _AuthGate(),
    );
  }
}

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
