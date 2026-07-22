import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:foodgad_mobile/common/create_dialog.dart';

/// The dropdown field added for product classification (#9): a `CreateField`
/// with `options` becomes a picker whose choice is returned like any other
/// field, and "no choice" comes back empty so the backend auto-classifies.
void main() {
  testWidgets('choosing a category returns it', (tester) async {
    Map<String, String>? captured;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => ElevatedButton(
              onPressed: () async {
                captured = await showCreateDialog(
                  ctx,
                  title: 'Nouveau produit',
                  fields: const [
                    CreateField('name', 'Nom', required: true),
                    CreateField('category', 'Catégorie',
                        options: ['Viande', 'Poisson'], emptyLabel: 'Automatique'),
                  ],
                );
              },
              child: const Text('open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).first, 'Steak haché');
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Viande').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Créer'));
    await tester.pumpAndSettle();

    expect(captured?['name'], 'Steak haché');
    expect(captured?['category'], 'Viande');
  });

  testWidgets('leaving the category unset returns empty (auto-classify)', (tester) async {
    Map<String, String>? captured;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (ctx) => ElevatedButton(
              onPressed: () async {
                captured = await showCreateDialog(
                  ctx,
                  title: 'Nouveau produit',
                  fields: const [
                    CreateField('name', 'Nom', required: true),
                    CreateField('category', 'Catégorie',
                        options: ['Viande', 'Poisson'], emptyLabel: 'Automatique'),
                  ],
                );
              },
              child: const Text('open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).first, 'Truc');
    await tester.tap(find.text('Créer'));
    await tester.pumpAndSettle();

    expect(captured?['name'], 'Truc');
    expect(captured?['category'], '');
  });
}
