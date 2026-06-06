import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';

final _productsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/products/', queryParameters: {'limit': 200});
  return resp.data as List<dynamic>;
});

class ProductsScreen extends ConsumerWidget {
  const ProductsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(_productsProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(_productsProvider);
        await ref.read(_productsProvider.future);
      },
      child: products.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(
          children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text('Erreur de chargement',
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          ],
        ),
        data: (rows) {
          if (rows.isEmpty) {
            return ListView(
              children: const [
                Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('Aucun produit. Ajoutez-en depuis le web ou l\'assistant.',
                      style: TextStyle(color: Colors.grey)),
                ),
              ],
            );
          }
          return ListView.separated(
            itemCount: rows.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final p = rows[i] as Map<String, dynamic>;
              return ListTile(
                leading: const Icon(Icons.inventory_2_outlined),
                title: Text('${p['name'] ?? ''}'),
                subtitle: p['sku'] != null ? Text('SKU ${p['sku']}') : null,
              );
            },
          );
        },
      ),
    );
  }
}
