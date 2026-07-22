import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:foodgad_mobile/core/api_client.dart';
import 'package:foodgad_mobile/core/providers.dart';
import 'package:foodgad_mobile/core/token_store.dart';
import 'package:foodgad_mobile/features/auth/auth_controller.dart';
import 'package:foodgad_mobile/features/invoices/invoice_detail_screen.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Fake backend for the invoice detail: answers the exact endpoints the screen
/// reads — GET /invoices/{id}, /invoices/{id}/lines, /products/enriched — with
/// the real JSON shapes returned by `backend/app/api/api_v1/endpoints/invoices.py`.
class _InvoiceApi implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.path;
    dynamic body;
    if (path.endsWith('/invoices/inv1/lines')) {
      body = [
        {
          'id': 'l1',
          'product_id': 'p1',
          'description': 'Farine T55 25kg',
          'qty': 2,
          'unit_id': 3,
          'unit_price': 18.5,
          'line_total': 37.0,
          'match_confidence': 91,
          'vat_rate': 5.5,
        },
        {
          'id': 'l2',
          'product_id': null,
          'description': 'Sucre semoule 25kg',
          'qty': 1,
          'unit_id': null,
          'unit_price': 24.9,
          'line_total': 24.9,
          'match_confidence': null,
        },
      ];
    } else if (path.endsWith('/invoices/inv1')) {
      body = {
        'id': 'inv1',
        'invoice_number': 'FT-2026-0042',
        'date': '2026-07-21',
        'total_amount': 173.97,
        'currency': 'EUR',
        'parsed': true,
        'ocr_status': 'parsed',
      };
    } else if (path.contains('/products/enriched')) {
      body = [
        {'id': 'p1', 'name': 'Farine', 'sku': 'FAR-01'},
        {'id': 'p2', 'name': 'Sucre', 'sku': null},
      ];
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

/// Authenticated admin, without hitting the network — so the write affordances
/// (edit pencil, add-line, delete) render in widget tests. `canWrite` = admin.
class _AdminAuth extends AuthController {
  @override
  AuthState build() => const AuthState(
        status: AuthStatus.authenticated,
        user: {
          'roles': ['admin'],
        },
      );
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });

  ProviderContainer makeContainer() {
    final client = ApiClient(TokenStore());
    client.dio.httpClientAdapter = _InvoiceApi();
    final c = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(client),
        authControllerProvider.overrideWith(_AdminAuth.new),
      ],
    );
    addTearDown(c.dispose);
    return c;
  }

  test('invoiceDetailProvider parses the invoice header', () async {
    final c = makeContainer();
    final inv = await c.read(invoiceDetailProvider('inv1').future);
    expect(inv['invoice_number'], 'FT-2026-0042');
    expect(inv['total_amount'], 173.97);
    expect(inv['currency'], 'EUR');
    expect(inv['parsed'], true);
  });

  test('invoiceLinesProvider parses every line and its fields', () async {
    final c = makeContainer();
    final lines = await c.read(invoiceLinesProvider('inv1').future);
    expect(lines.length, 2);

    final mapped = lines.first;
    expect(mapped['description'], 'Farine T55 25kg');
    expect(mapped['qty'], 2);
    expect(mapped['unit_price'], 18.5);
    expect(mapped['line_total'], 37.0);
    expect(mapped['product_id'], 'p1'); // mapped line
    expect(mapped['match_confidence'], 91);

    final unmapped = lines[1];
    expect(unmapped['product_id'], isNull); // "À revoir" branch
  });

  test('a line without product_id counts as needing review', () async {
    final c = makeContainer();
    final lines = await c.read(invoiceLinesProvider('inv1').future);
    final needsReview = lines.where((l) => l['product_id'] == null).length;
    expect(needsReview, 1, reason: 'the banner "N ligne(s) à associer" depends on this');
  });

  Future<void> pumpScreen(WidgetTester tester, ProviderContainer c) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: c,
      child: const MaterialApp(
        home: InvoiceDetailScreen(invoiceId: 'inv1'),
      ),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets('a line with vat_rate shows the "TVA x%" suffix, and the mapped '
      'line exposes the chevron that opens the product', (tester) async {
    final c = makeContainer();
    await pumpScreen(tester, c);

    // #8 — the VAT persisted on a line renders on its card.
    expect(find.textContaining('TVA 5,5%'), findsOneWidget);
    // #8 — the mapped product cell is tappable (chevron → ProductDetailScreen).
    expect(find.byIcon(Icons.chevron_right), findsWidgets);
    // The unmapped line still shows the "À revoir" branch.
    expect(find.text('À revoir'), findsOneWidget);
  });

  testWidgets('the line edit dialog exposes a "TVA %" field pre-filled from the '
      'line', (tester) async {
    final c = makeContainer();
    await pumpScreen(tester, c);

    // Open the first line's "Corriger" dialog.
    await tester.tap(find.byTooltip('Corriger').first);
    await tester.pumpAndSettle();

    expect(find.text('Corriger la ligne'), findsOneWidget);
    // #8 — the new VAT field is present…
    expect(find.text('TVA %'), findsOneWidget);
    // …and pre-filled with the line's persisted value (5.5 -> "5,5").
    expect(find.text('5,5'), findsOneWidget);
  });
}
