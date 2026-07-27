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
import 'package:foodgad_mobile/features/suppliers/supplier_detail_screen.dart';

/// Faux backend : sert les 4 endpoints que lit l'écran, avec un bloc `savings`
/// dans l'overview (shape de `savings_service.for_supplier`).
class _SupplierApi implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? _,
      Future<void>? __) async {
    final path = options.path;
    dynamic body;
    if (path.endsWith('/suppliers/s1/overview')) {
      body = {
        'supplier_id': 's1',
        'supplier_name': 'METRO',
        'annual_amount': 1850.0,
        'score': null,
        'conformity_rate': null,
        'on_time_rate': null,
        'late_count': 0,
        'receipt_count': 0,
        'quote_count': 1,
        'order_count': 1,
        'invoice_count': 0,
        'distinct_products': 1,
        'monthly': [],
        'top_products': [],
        'price_trend_pct': null,
        'orders_by_status': {},
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
      };
    } else if (path.endsWith('/suppliers/s1/purchase-history')) {
      body = {'purchases': []};
    } else if (path.endsWith('/suppliers/s1/prices')) {
      body = [];
    } else if (path.endsWith('/suppliers/s1')) {
      body = {'id': 's1', 'name': 'METRO', 'contact': {}, 'rating': null};
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

  testWidgets('the supplier fiche shows the Économies block', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final client = ApiClient(TokenStore());
    client.dio.httpClientAdapter = _SupplierApi();

    await tester.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(client)],
      child: const MaterialApp(
        home: SupplierDetailScreen(supplierId: 's1', supplierName: 'METRO'),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('Économies (12 mois)'), findsOneWidget);
    expect(find.text('Économisé'), findsOneWidget);
    expect(find.text('Taux de meilleur choix'), findsOneWidget);
  });
}
