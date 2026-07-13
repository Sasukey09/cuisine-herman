import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_error.dart';
import '../core/outbox.dart';
import '../core/providers.dart';

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

/// Create now, or keep the intent for when the network comes back.
///
/// Tapping "Créer" in the cellar used to lose the work outright: an error toast,
/// and the product was gone. Now a *connection* failure queues the write; a
/// server refusal (a 400, a duplicate) is still reported, because retrying it
/// forever would only hide the problem.
Future<void> createOrQueue(
  WidgetRef ref,
  ScaffoldMessengerState messenger, {
  required String path,
  required Map<String, dynamic> body,
  required String label,
  required String successMessage,
  VoidCallback? onDone,
}) async {
  try {
    await ref.read(apiClientProvider).dio.post(path, data: body);
    messenger.showSnackBar(SnackBar(content: Text(successMessage)));
  } catch (e) {
    if (!isOfflineError(e)) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
      return;
    }
    final outbox = await ref.read(outboxProvider.future);
    await outbox.enqueue(path: path, body: body, label: label);
    messenger.showSnackBar(SnackBar(
      content: Text('Hors connexion — « $label » sera envoyé dès le retour du réseau.'),
      duration: const Duration(seconds: 4),
    ));
  } finally {
    onDone?.call();
  }
}
