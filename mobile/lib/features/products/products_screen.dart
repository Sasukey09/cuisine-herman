import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kBorder, kCard;

final _query = StateProvider.autoDispose<String>((ref) => '');

final _productsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final q = ref.watch(_query).trim();
  final resp = await ref.read(apiClientProvider).dio.get('/products/enriched', queryParameters: {
    'limit': 200,
    if (q.isNotEmpty) 'q': q,
  });
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
      body: asyncCardList(
        ref: ref,
        provider: _productsProvider,
        empty: 'Aucun produit. Touchez + pour en ajouter.',
        header: _SearchPill(onChanged: (v) => ref.read(_query.notifier).state = v),
        itemBuilder: (p) {
          final sub = [p['category'], p['supplier']]
              .where((e) => e != null && '$e'.isNotEmpty)
              .join(' · ');
          return MockCard(
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${p['name'] ?? ''}',
                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 2),
                      Text(sub.isEmpty ? 'Produit' : sub,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12, color: kMuted)),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(eur(p['last_cost'] as num?),
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    TrendBadge(p['variation_pct'] as num?),
                  ],
                ),
              ],
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _create(context, ref),
        child: const Icon(Icons.add),
      ),
    );
  }
}

class _SearchPill extends StatelessWidget {
  const _SearchPill({required this.onChanged});
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: kCard,
        border: Border.all(color: kBorder),
        borderRadius: BorderRadius.circular(11),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Row(
        children: [
          const Icon(Icons.search, size: 16, color: kMuted),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              onChanged: onChanged,
              style: const TextStyle(fontSize: 13),
              decoration: const InputDecoration(
                isCollapsed: true,
                border: InputBorder.none,
                hintText: 'Rechercher un produit…',
                hintStyle: TextStyle(fontSize: 13, color: kMuted),
                contentPadding: EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
