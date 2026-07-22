import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:foodgad_mobile/app/home_shell.dart';
import 'package:foodgad_mobile/core/api_client.dart';
import 'package:foodgad_mobile/core/providers.dart';
import 'package:foodgad_mobile/core/token_store.dart';
import 'package:foodgad_mobile/features/auth/auth_controller.dart';

/// Answers every request with an empty JSON object so the shell's child screens
/// settle into an (empty/error) state without hanging — the test only cares
/// about the shell chrome (the back affordance), not the screen contents.
class _EmptyApi implements HttpClientAdapter {
  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<List<int>>? requestStream,
      Future<void>? cancelFuture) async {
    return ResponseBody.fromString(
      jsonEncode({}),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }
}

/// Authenticated without touching the network.
class _FakeAuth extends AuthController {
  @override
  AuthState build() => const AuthState(
        status: AuthStatus.authenticated,
        user: {
          'name': 'Chef',
          'roles': ['admin'],
        },
      );
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });

  Future<void> pumpShell(WidgetTester tester) async {
    // A phone-sized surface: the default 800×600 test window is too short for
    // the shell (header + content + bottom nav) and overflows, which breaks
    // hit-testing.
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final client = ApiClient(TokenStore());
    client.dio.httpClientAdapter = _EmptyApi();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(client),
          authControllerProvider.overrideWith(_FakeAuth.new),
        ],
        child: const MaterialApp(home: HomeShell()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 300));
  }

  // ------------------------------------------------------------------------ //
  // #4: a secondary module (Import vidéo…) is mounted inside the shell, not
  // pushed as a route, so it has no automatic back arrow. The shell must give
  // one — the chef must never be stuck on a page with no visible way out.
  // ------------------------------------------------------------------------ //
  testWidgets('a primary tab shows no back arrow; a secondary module does, and it returns home',
      (tester) async {
    await pumpShell(tester);

    // On the primary "Accueil" tab: no back arrow.
    expect(find.byIcon(Icons.arrow_back), findsNothing);

    // Open the "Plus" sheet and pick a secondary module.
    await tester.tap(find.text('Plus'));
    await tester.pump(); // start the sheet animation
    await tester.pump(const Duration(milliseconds: 400)); // let it settle
    final videoTile = find.text('Import vidéo').last;
    await tester.ensureVisible(videoTile);
    await tester.tap(videoTile);
    await tester.pump(const Duration(milliseconds: 400));

    // Now on a secondary module: the back arrow is visible.
    expect(find.byIcon(Icons.arrow_back), findsOneWidget);

    // Tapping it returns to a primary tab (arrow gone again).
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byIcon(Icons.arrow_back), findsNothing);
  });
}
