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
///
/// The controllers are owned by a StatefulWidget so they are disposed only when
/// the route is fully gone — disposing them right after `showDialog` returns
/// would crash during the close animation, which still rebuilds the fields
/// (`'_dependents.isEmpty': is not true`). Mirrors [showEditDialog].
Future<Map<String, String>?> showCreateDialog(
  BuildContext context, {
  required String title,
  required List<CreateField> fields,
}) {
  return showDialog<Map<String, String>>(
    context: context,
    builder: (ctx) => _CreateDialog(title: title, fields: fields),
  );
}

class _CreateDialog extends StatefulWidget {
  const _CreateDialog({required this.title, required this.fields});
  final String title;
  final List<CreateField> fields;

  @override
  State<_CreateDialog> createState() => _CreateDialogState();
}

class _CreateDialogState extends State<_CreateDialog> {
  final _formKey = GlobalKey<FormState>();
  late final Map<String, TextEditingController> _controllers = {
    for (final f in widget.fields) f.key: TextEditingController()
  };

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: widget.fields
                .map((f) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: TextFormField(
                        controller: _controllers[f.key],
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
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            if (_formKey.currentState!.validate()) {
              Navigator.pop(context,
                  {for (final f in widget.fields) f.key: _controllers[f.key]!.text.trim()});
            }
          },
          child: const Text('Créer'),
        ),
      ],
    );
  }
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
