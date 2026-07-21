import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:foodgad_mobile/core/api_client.dart';
import 'package:foodgad_mobile/core/providers.dart';
import 'package:foodgad_mobile/core/token_store.dart';
import 'package:foodgad_mobile/features/products/products_screen.dart';

/// Fake HTTP layer: answers `GET /products/enriched` by filtering a fixed
/// catalogue on the `q` query parameter — exactly like the backend's ilike.
/// If the provider does NOT forward the search term, `q` is empty here and the
/// full list comes back: that is precisely the bug this test guards against.
class _FilteringAdapter implements HttpClientAdapter {
  final catalogue = const [
    {'id': '1', 'name': 'Beurre doux'},
    {'id': '2', 'name': 'Farine T55'},
  ];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final q = (options.queryParameters['q'] as String? ?? '').toLowerCase();
    final rows = q.isEmpty
        ? catalogue
        : catalogue
            .where((p) => (p['name'] as String).toLowerCase().contains(q))
            .toList();
    return ResponseBody.fromString(
      jsonEncode(rows),
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

  // ---------------------------------------------------------------------- //
  // Regression: the product search box did nothing.
  //
  // `productsListProvider` read `productsSearchQueryProvider` *after* an await
  // (inside fetchWithCache's request closure), so Riverpod never registered the
  // dependency. Typing updated the query state but never re-ran the fetch: the
  // list ignored the search entirely. A non-matching query must empty the list.
  // ---------------------------------------------------------------------- //
  test('changing the search query re-runs the fetch and filters the list',
      () async {
    final client = ApiClient(TokenStore());
    client.dio.httpClientAdapter = _FilteringAdapter();

    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(client)],
    );
    addTearDown(container.dispose);
    // Keep the autoDispose providers alive across recomputes.
    final sub = container.listen(productsListProvider, (_, __) {});
    addTearDown(sub.close);

    // Empty query -> the whole catalogue.
    final all = await container.read(productsListProvider.future);
    expect((all.data as List).length, 2);

    // A matching query -> only the matching row.
    container.read(productsSearchQueryProvider.notifier).state = 'farine';
    final matched = await container.read(productsListProvider.future);
    expect((matched.data as List).length, 1);
    expect(((matched.data as List).first as Map)['name'], 'Farine T55');

    // A non-matching query -> an empty list. Before the fix this still returned
    // the full catalogue, which is exactly what the user saw on the emulator.
    container.read(productsSearchQueryProvider.notifier).state = 'zzzznope';
    final none = await container.read(productsListProvider.future);
    expect((none.data as List), isEmpty);
  });
}
