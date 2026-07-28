import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:foodgad_mobile/core/api_client.dart';
import 'package:foodgad_mobile/core/providers.dart';
import 'package:foodgad_mobile/core/token_store.dart';
import 'package:foodgad_mobile/features/products/product_detail_screen.dart';

/// Faux backend : sert `/products/p1/overview` (fiche 360°) + les autres
/// endpoints que la fiche produit appelle au chargement de ses six onglets,
/// avec un corps vide mais bien formé (`{}`/`[]`) pour ne pas faire planter
/// les onglets qui ne sont pas sous test ici.
class _ProductApi implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? _,
      Future<void>? __) async {
    final path = options.path;
    dynamic body;
    if (path.endsWith('/products/p1/overview')) {
      body = {
        'product_id': 'p1',
        'product_name': 'Beurre',
        'category': null,
        'unit_code': null,
        'annual_amount': 385.0,
        'monthly': [],
        'purchase_count': 2,
        'supplier_count': 2,
        'recipe_count': 1,
        'offer_count': 1,
        'cheapest_supplier': {'supplier_id': 'm', 'supplier_name': 'METRO', 'cost': 18.0},
        'last_cost': 20.0,
        'avg_cost': 19.25,
        'best_cost': 18.5,
        'price_trend_pct': 8.0,
        'offers': {
          'best_price': 18.0,
          'best_supplier_name': 'METRO',
          'latest_price': 18.0,
          'avg_price': 18.0,
          'supplier_count': 1,
        },
        'savings': {
          'realized': 20.0,
          'missed': 0.0,
          'possible': 20.0,
          'best_choice_rate': 1.0,
          'compared_lines': 1,
          'labels': {
            'realized': 'Économisé',
            'missed': 'Laissé sur la table',
            'possible': 'Économie possible',
            'best_choice_rate': 'Taux de meilleur choix',
          },
        },
        'top_suppliers': [
          {'supplier_id': 'm', 'supplier_name': 'METRO', 'amount': 185.0, 'count': 1, 'is_cheapest': true},
        ],
      };
    } else if (path.endsWith('/products/p1/suppliers')) {
      body = {'suppliers': []};
    } else if (path.endsWith('/products/p1/price-history')) {
      body = {'purchases': []};
    } else if (path.endsWith('/products/p1/invoices')) {
      body = {'invoices': []};
    } else if (path.endsWith('/products/p1/recipes')) {
      body = {'recipes': []};
    } else if (path.endsWith('/products/p1/quote-history')) {
      body = {'offers': []};
    } else if (path.endsWith('/products/p1')) {
      body = {'id': 'p1', 'name': 'Beurre'};
    } else {
      body = {};
    }
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {Headers.contentTypeHeader: [Headers.jsonContentType]},
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

  testWidgets("the product fiche shows the Vue d'ensemble scorecard", (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final client = ApiClient(TokenStore());
    client.dio.httpClientAdapter = _ProductApi();

    await tester.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(client)],
      child: const MaterialApp(
        home: ProductDetailScreen(productId: 'p1', productName: 'Beurre'),
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text("Vue d'ensemble"));
    await tester.pumpAndSettle();

    expect(find.textContaining('Payé sur 12 mois'), findsOneWidget);
    expect(find.text('Économisé'), findsOneWidget);
  });
}
