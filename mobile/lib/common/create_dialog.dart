import 'package:flutter/material.dart';

class CreateField {
  const CreateField(this.key, this.label, {this.keyboard = TextInputType.text, this.required = false});
  final String key;
  final String label;
  final TextInputType keyboard;
  final bool required;
}

/// Generic "create" form dialog. Returns the entered values (trimmed) or null
/// if cancelled. Keeps the list screens free of per-form boilerplate.
Future<Map<String, String>?> showCreateDialog(
  BuildContext context, {
  required String title,
  required List<CreateField> fields,
}) async {
  final controllers = {for (final f in fields) f.key: TextEditingController()};
  final formKey = GlobalKey<FormState>();

  final result = await showDialog<Map<String, String>>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Form(
        key: formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: fields
                .map((f) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: TextFormField(
                        controller: controllers[f.key],
                        keyboardType: f.keyboard,
                        decoration: InputDecoration(labelText: f.label),
                        validator: (v) => f.required && (v == null || v.trim().isEmpty)
                            ? 'Requis'
                            : null,
                      ),
                    ))
                .toList(),
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            if (formKey.currentState!.validate()) {
              Navigator.pop(ctx, {for (final f in fields) f.key: controllers[f.key]!.text.trim()});
            }
          },
          child: const Text('Créer'),
        ),
      ],
    ),
  );

  for (final c in controllers.values) {
    c.dispose();
  }
  return result;
}
