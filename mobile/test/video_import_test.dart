import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:foodgad_mobile/core/api_client.dart';
import 'package:foodgad_mobile/core/providers.dart';
import 'package:foodgad_mobile/core/token_store.dart';
import 'package:foodgad_mobile/features/video/video_import_screen.dart';

/// Fake backend for the video import screen.
///
/// Answers ANY `/video/extract*` path (extract, extract-transcript,
/// extract-file) with the SAME multi-recipe shape returned by
/// `backend/app/schemas/schemas.py::VideoExtractResult` — a `candidates` list
/// plus a `source`. The screen only reaches `/video/extract` in this test: a
/// non-YouTube URL skips the on-device caption fetch (`_fetchYoutubeCaptions`,
/// which hits the real network via youtube_explode_dart and has no place in a
/// widget test), so it falls straight to POST /video/extract. Matching on
/// `/video/extract` (a prefix of all three routes) keeps the fake honest for
/// whichever one actually fires.
class _VideoApi implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.path;
    dynamic body;
    if (path.contains('/video/extract')) {
      body = {
        'source_id': 'src1',
        'platform': 'youtube',
        'transcript_source': 'youtube_captions',
        'transcript_excerpt': '…',
        'note': '',
        'source': {
          'platform': 'youtube',
          'url': 'https://example.com/video',
          'video_id': 'abc123',
          'title': 'Deux recettes',
          'creator': 'Chef',
          'thumbnail': null,
        },
        'candidates': [
          {
            'name': 'Pâtes',
            'description': null,
            'summary': null,
            'yield_qty': 4,
            'ingredients': [
              {'name': 'Pâtes', 'qty': 400, 'unit': 'g'},
              {'name': 'Beurre', 'qty': 50, 'unit': 'g'},
            ],
            'steps': ['Cuire les pâtes', 'Ajouter le beurre'],
            'prep_time_min': 5,
            'cook_time_min': 10,
            'tips': [],
            'variants': [],
            'allergens': [],
            'start_sec': 0,
            'end_sec': 120,
          },
          {
            'name': 'Salade',
            'description': null,
            'summary': null,
            'yield_qty': 2,
            'ingredients': [
              {'name': 'Salade verte', 'qty': 1, 'unit': 'pièce'},
            ],
            'steps': ['Laver la salade', 'Assaisonner'],
            'prep_time_min': 5,
            'cook_time_min': null,
            'tips': [],
            'variants': [],
            'allergens': [],
            'start_sec': 120,
            'end_sec': 200,
          },
        ],
      };
    } else if (path.contains('/video/save')) {
      // Both candidates are selected by default, so the common "Enregistrer
      // N sélectionnées" flow submits both — the response mirrors that. The
      // backend saves recipe by recipe and returns a partial success: each saved
      // entry carries its input `index`, plus an `errors` list (empty here).
      body = {
        'count': 2,
        'recipes': [
          {
            'index': 0,
            'recipe_id': 'r1',
            'version_id': 'v1',
            'name': 'Pâtes',
            'yield_qty': 4,
            'unmatched_ingredients': [],
            'cost': {
              'computed_cost_total': 5.2,
              'cost_per_portion': 1.3,
              'food_cost_pct': 12.0,
              'has_missing_prices': false,
            },
            'note': '',
          },
          {
            'index': 1,
            'recipe_id': 'r2',
            'version_id': 'v2',
            'name': 'Salade',
            'yield_qty': 2,
            'unmatched_ingredients': [],
            'cost': {
              'computed_cost_total': 2.4,
              'cost_per_portion': 1.2,
              'food_cost_pct': 10.0,
              'has_missing_prices': false,
            },
            'note': '',
          },
        ],
        'errors': [],
      };
    } else {
      body = {};
    }
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });

  ProviderContainer makeContainer() {
    final client = ApiClient(TokenStore());
    client.dio.httpClientAdapter = _VideoApi();
    final c = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(client)],
    );
    addTearDown(c.dispose);
    return c;
  }

  Future<void> pumpScreen(WidgetTester tester, ProviderContainer c) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: c,
      child: const MaterialApp(
        home: Scaffold(body: VideoImportScreen()),
      ),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets(
      'extracting a video with two recipes shows a "2 recette(s)" header and '
      'both recipe names', (tester) async {
    final c = makeContainer();
    await pumpScreen(tester, c);

    // A non-YouTube URL: `_fetchYoutubeCaptions` never fires, so the screen
    // posts straight to POST /video/extract.
    await tester.enterText(find.byType(TextField).first, 'https://example.com/video');
    await tester.tap(find.text('Analyser'));
    await tester.pumpAndSettle();

    expect(find.textContaining('2 recette'), findsOneWidget);
    expect(find.text('Pâtes'), findsOneWidget);
    expect(find.text('Salade'), findsOneWidget);
  });

  testWidgets(
      'saving all detected recipes (the default, everything-selected path) '
      'shows the confirmation banner, not just the transient snackbar',
      (tester) async {
    final c = makeContainer();
    await pumpScreen(tester, c);

    await tester.enterText(find.byType(TextField).first, 'https://example.com/video');
    await tester.tap(find.text('Analyser'));
    await tester.pumpAndSettle();

    // Both candidates default to selected -> this is "Enregistrer 2
    // sélectionnées", i.e. save-everything. That's exactly the path that used
    // to empty `_candidates` and, with it, hide the `_savedInfo` banner
    // (which was nested inside `if (_candidates.isNotEmpty)`): regression
    // guard for that bug.
    await tester.tap(find.textContaining('Enregistrer'));
    await tester.pumpAndSettle();

    // Distinct to the banner text (built from the /video/save response's
    // per-recipe cost), not the transient SnackBar wording — so this only
    // passes if the banner itself actually painted.
    expect(find.textContaining('€/portion'), findsOneWidget);
    expect(find.textContaining('Pâtes'), findsWidgets);
    expect(find.textContaining('Salade'), findsWidgets);
  });
}
