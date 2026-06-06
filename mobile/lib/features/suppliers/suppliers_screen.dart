import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';

final _suppliersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/');
  return resp.data as List<dynamic>;
});

class SuppliersScreen extends ConsumerWidget {
  const SuppliersScreen({super.key});

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final data = await showCreateDialog(context, title: 'Nouveau fournisseur', fields: const [
      CreateField('name', 'Nom', required: true),
      CreateField('code', 'Code (optionnel)'),
    ]);
    if (data == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/suppliers/', data: {
        'name': data['name'],
        if ((data['code'] ?? '').isNotEmpty) 'code': data['code'],
      });
      ref.invalidate(_suppliersProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Fournisseur créé.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: asyncListView(
        ref: ref,
        provider: _suppliersProvider,
        empty: 'Aucun fournisseur. Touchez + pour en ajouter.',
        itemBuilder: (s) => ListTile(
          leading: const Icon(Icons.local_shipping_outlined),
          title: Text('${s['name'] ?? ''}'),
          subtitle: s['code'] != null ? Text('Code ${s['code']}') : null,
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _create(context, ref),
        child: const Icon(Icons.add),
      ),
    );
  }
}
