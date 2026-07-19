// I7 — CRUD helpers: the long-press action sheet and the pre-filled edit dialog.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:foodgad_mobile/common/create_dialog.dart';
import 'package:foodgad_mobile/common/edit_delete.dart';

Widget _host(void Function(BuildContext) onTap) {
  return MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (context) => Center(
          child: ElevatedButton(
            onPressed: () => onTap(context),
            child: const Text('go'),
          ),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('showRowActions returns "edit" when Modifier is tapped', (tester) async {
    String? result = 'unset';
    await tester.pumpWidget(_host((ctx) async {
      result = await showRowActions(ctx);
    }));

    await tester.tap(find.text('go'));
    await tester.pumpAndSettle();
    expect(find.text('Modifier'), findsOneWidget);
    expect(find.text('Supprimer'), findsOneWidget);

    await tester.tap(find.text('Modifier'));
    await tester.pumpAndSettle();
    expect(result, 'edit');
  });

  testWidgets('showRowActions returns "delete" when Supprimer is tapped', (tester) async {
    String? result = 'unset';
    await tester.pumpWidget(_host((ctx) async {
      result = await showRowActions(ctx);
    }));
    await tester.tap(find.text('go'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Supprimer'));
    await tester.pumpAndSettle();
    expect(result, 'delete');
  });

  testWidgets('showEditDialog is pre-filled and returns edited values', (tester) async {
    Map<String, String>? result;
    await tester.pumpWidget(_host((ctx) async {
      result = await showEditDialog(
        ctx,
        title: 'Modifier le produit',
        fields: const [
          CreateField('name', 'Nom', required: true),
          CreateField('sku', 'SKU (optionnel)'),
        ],
        initial: {'name': 'Tomate', 'sku': 'TOM-1'},
      );
    }));

    await tester.tap(find.text('go'));
    await tester.pumpAndSettle();

    // pre-filled with the initial values
    expect(find.text('Tomate'), findsOneWidget);
    expect(find.text('TOM-1'), findsOneWidget);

    // edit the name, then save
    await tester.enterText(find.widgetWithText(TextFormField, 'Tomate'), 'Tomate cerise');
    await tester.tap(find.text('Enregistrer'));
    await tester.pumpAndSettle();

    expect(result, {'name': 'Tomate cerise', 'sku': 'TOM-1'});
  });

  testWidgets('showEditDialog blocks saving when a required field is emptied', (tester) async {
    Map<String, String>? result = {'sentinel': 'still-open'};
    await tester.pumpWidget(_host((ctx) async {
      result = await showEditDialog(
        ctx,
        title: 'Modifier',
        fields: const [CreateField('name', 'Nom', required: true)],
        initial: {'name': 'X'},
      );
    }));
    await tester.tap(find.text('go'));
    await tester.pumpAndSettle();

    await tester.enterText(find.widgetWithText(TextFormField, 'X'), '');
    await tester.tap(find.text('Enregistrer'));
    await tester.pumpAndSettle();

    // still open, validation error shown, nothing returned
    expect(find.text('Requis'), findsOneWidget);
    expect(result, {'sentinel': 'still-open'});
  });
}
