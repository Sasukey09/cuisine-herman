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
import 'package:foodgad_mobile/features/pilotage/pilotage_screen.dart';

/// Fake backend for the Pilotage Achats screen. Answers `/purchasing/kpi`
/// with the same shape as `backend/app/services/purchasing/kpi_service.py`
/// (`savings`/`possible_open`/`cycle`/`price`/`top_products`/`suppliers`/
/// `labels`) — see the web `PurchasingKpi` type in
/// `frontend/src/services/types.ts` (Task 2/3 of this feature).
class _KpiApi implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    dynamic body;
    if (options.path.contains('/purchasing/kpi')) {
      body = {
        'window_months': 12,
        'savings': {
          'realized': 320.5,
          'missed': 45.0,
          'possible': 365.5,
          'best_choice_rate': 0.82,
          'compared_lines': 40,
          'labels': {
            'realized': 'Économisé',
            'missed': 'Laissé sur la table',
            'possible': 'Économie possible',
            'best_choice_rate': 'Taux de meilleur choix',
          },
        },
        'possible_open': 120.0,
        'cycle': {
          'ordered_total': 1000.0,
          'received_value': 700.0,
          'billed_total': 650.0,
          'gap_ordered_received': 300.0,
          'gap_billed_received': -50.0,
          'missing_value': 300.0,
          'ordered_by_status': {},
        },
        'price': {
          'n_hausse': 2,
          'n_baisse': 1,
          'top_inflation_pct': 8.5,
          'n_critiques': 1,
          'switch_savings_total': 40.0,
        },
        'top_products': [],
        'suppliers': {
          'most_competitive': [],
          'most_late': [],
          'best_conformity': [],
        },
        'labels': {
          'ordered_total': 'Commandé',
          'received_value': 'Reçu',
          'billed_total': 'Facturé',
          'gap_ordered_received': 'Écart commandé → reçu',
          'gap_billed_received': 'Écart facturé → reçu',
          'missing_value': 'En attente de livraison',
          'possible_open': 'Économies possibles (devis ouverts)',
          'most_competitive': 'Plus compétitifs',
          'most_late': 'En retard',
          'best_conformity': 'Meilleure conformité',
        },
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
    client.dio.httpClientAdapter = _KpiApi();
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
        home: Scaffold(body: PilotageScreen()),
      ),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets(
      'Pilotage Achats renders the header plus the Économisé and Commandé tiles',
      (tester) async {
    final c = makeContainer();
    await pumpScreen(tester, c);

    expect(find.textContaining('Pilotage'), findsWidgets);
    expect(find.textContaining('Économisé'), findsOneWidget);
    expect(find.textContaining('Commandé'), findsOneWidget);
  });
}
