// Basic smoke test for the FoodGad mobile app.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:foodgad_mobile/main.dart';

void main() {
  testWidgets('App boots into a MaterialApp', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: FoodGadApp()));
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
