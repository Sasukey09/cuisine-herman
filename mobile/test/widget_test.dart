// Basic smoke test for the Cuisine Herman mobile app.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:cuisine_herman_mobile/main.dart';

void main() {
  testWidgets('App boots into a MaterialApp', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: CuisineHermanApp()));
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
