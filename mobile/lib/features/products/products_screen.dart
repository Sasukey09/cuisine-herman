import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';

final _productsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/', queryParameters: {'limit': 200});
  return resp.data as List<dynamic>;
});

class ProductsScreen extends ConsumerWidget {
  const ProductsScreen({super.key});

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final data = await showCreateDialog(context, title: 'Nouveau produit', fields: const [
      CreateField('name', 'Nom', required: true),
      CreateField('sku', 'SKU (optionnel)'),
    ]);
    if (data == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/products/', data: {
        'name': data['name'],
        if ((data['sku'] ?? '').isNotEmpty) 'sku': data['sku'],
      });
      ref.invalidate(_productsProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Produit créé.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: asyncListView(
        ref: ref,
        provider: _productsProvider,
        empty: 'Aucun produit. Touchez + pour en ajouter.',
        itemBuilder: (p) => ListTile(
          leading: const Icon(Icons.inventory_2_outlined),
          title: Text('${p['name'] ?? ''}'),
          subtitle: p['sku'] != null ? Text('SKU ${p['sku']}') : null,
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _create(context, ref),
        child: const Icon(Icons.add),
      ),
    );
  }
}
