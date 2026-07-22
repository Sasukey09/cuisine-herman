import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_error.dart';
import '../core/providers.dart';
import 'create_dialog.dart';

/// Edit form pre-filled with [initial]. Returns edited (trimmed) values, or null
/// if cancelled. Mirrors [showCreateDialog] but with a "Enregistrer" action.
///
/// The controllers are owned by a StatefulWidget so they are disposed only when
/// the route is fully gone — disposing them right after `showDialog` returns
/// would crash during the close animation, which still rebuilds the fields.
Future<Map<String, String>?> showEditDialog(
  BuildContext context, {
  required String title,
  required List<CreateField> fields,
  required Map<String, String> initial,
}) {
  return showDialog<Map<String, String>>(
    context: context,
    builder: (ctx) => _EditDialog(title: title, fields: fields, initial: initial),
  );
}

class _EditDialog extends StatefulWidget {
  const _EditDialog({required this.title, required this.fields, required this.initial});
  final String title;
  final List<CreateField> fields;
  final Map<String, String> initial;

  @override
  State<_EditDialog> createState() => _EditDialogState();
}

class _EditDialogState extends State<_EditDialog> {
  final _formKey = GlobalKey<FormState>();
  late final Map<String, TextEditingController> _controllers = {
    for (final f in widget.fields)
      f.key: TextEditingController(text: widget.initial[f.key] ?? '')
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
                .map((f) => buildDialogField(f, _controllers[f.key]!))
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
          child: const Text('Enregistrer'),
        ),
      ],
    );
  }
}

/// PUT an update. Reports any error (including offline — unlike creates, edits
/// are not queued: a stale offline edit is more surprising than an explicit
/// "try again online").
Future<void> updateEntity(
  WidgetRef ref,
  ScaffoldMessengerState messenger, {
  required String path,
  required Map<String, dynamic> body,
  required String successMessage,
  VoidCallback? onDone,
}) async {
  try {
    await ref.read(apiClientProvider).dio.put(path, data: body);
    messenger.showSnackBar(SnackBar(content: Text(successMessage)));
    onDone?.call();
  } catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
  }
}

/// Confirm, then DELETE. Surfaces the server message on refusal — e.g. a 409 when
/// the row is still referenced (a product used by a recipe), so the user learns
/// why instead of seeing a silent no-op.
Future<void> confirmAndDelete(
  BuildContext context,
  WidgetRef ref,
  ScaffoldMessengerState messenger, {
  required String path,
  required String name,
  required String successMessage,
  VoidCallback? onDone,
}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Supprimer ?'),
      content: Text('Supprimer « $name » ? Cette action est définitive.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Supprimer')),
      ],
    ),
  );
  if (ok != true) return;
  try {
    await ref.read(apiClientProvider).dio.delete(path);
    messenger.showSnackBar(SnackBar(content: Text(successMessage)));
    onDone?.call();
  } catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
  }
}

/// Long-press action sheet. Returns 'edit', 'delete', or null.
Future<String?> showRowActions(BuildContext context) {
  return showModalBottomSheet<String>(
    context: context,
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.edit_outlined),
            title: const Text('Modifier'),
            onTap: () => Navigator.pop(ctx, 'edit'),
          ),
          ListTile(
            leading: const Icon(Icons.delete_outline),
            title: const Text('Supprimer'),
            onTap: () => Navigator.pop(ctx, 'delete'),
          ),
        ],
      ),
    ),
  );
}
