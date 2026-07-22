import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/edit_delete.dart';
import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kCategoryColors;
import '../auth/auth_controller.dart';
import 'product_detail_screen.dart';

@visibleForTesting
final productsSearchQueryProvider = StateProvider.autoDispose<String>((ref) => '');

@visibleForTesting
final productsListProvider = FutureProvider.autoDispose<Loaded>((ref) async {
  // Watch the search query *synchronously*, before any await. Reading it inside
  // the request closure — after fetchWithCache's first await — never registered
  // the reactive dependency, so typing in the search box updated the query but
  // never re-ran this provider: the list silently ignored the search entirely.
  final q = ref.watch(productsSearchQueryProvider).trim();
  return fetchWithCache(ref, cacheKey: 'products', request: () async {
    final resp = await ref.read(apiClientProvider).dio.get('/products/enriched', queryParameters: {
      'limit': 200,
      if (q.isNotEmpty) 'q': q,
    });
    return resp.data;
  });
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
    await createOrQueue(
      ref,
      messenger,
      path: '/products/',
      body: {
        'name': data['name'],
        if ((data['sku'] ?? '').isNotEmpty) 'sku': data['sku'],
      },
      label: 'Produit : ${data['name']}',
      successMessage: 'Produit créé.',
      onDone: () => ref.invalidate(productsListProvider),
    );
  }

  Future<void> _actions(BuildContext context, WidgetRef ref, Map<String, dynamic> p) async {
    final messenger = ScaffoldMessenger.of(context);
    final action = await showRowActions(context);
    if (action == null || !context.mounted) return;
    if (action == 'edit') {
      final data = await showEditDialog(
        context,
        title: 'Modifier le produit',
        fields: const [
          CreateField('name', 'Nom', required: true),
          CreateField('sku', 'SKU (optionnel)'),
        ],
        initial: {'name': '${p['name'] ?? ''}', 'sku': '${p['sku'] ?? ''}'},
      );
      if (data == null) return;
      await updateEntity(
        ref,
        messenger,
        path: '/products/${p['id']}',
        body: {
          'name': data['name'],
          'sku': (data['sku'] ?? '').isEmpty ? null : data['sku'],
        },
        successMessage: 'Produit modifié.',
        onDone: () => ref.invalidate(productsListProvider),
      );
    } else {
      await confirmAndDelete(
        context,
        ref,
        messenger,
        path: '/products/${p['id']}',
        name: '${p['name'] ?? ''}',
        successMessage: 'Produit supprimé.',
        onDone: () => ref.invalidate(productsListProvider),
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canWrite = ref.watch(canWriteProvider);
    return Scaffold(
      body: offlineCardList(
        ref: ref,
        provider: productsListProvider,
        empty: 'Aucun produit. Touchez + pour en ajouter.',
        header: Column(children: [
          const PendingWritesBanner(),
          _SearchPill(onChanged: (v) => ref.read(productsSearchQueryProvider.notifier).state = v),
        ]),
        itemBuilder: (p) {
          final name = '${p['name'] ?? ''}';
          final category = '${p['category'] ?? ''}';
          final chipColor = kCategoryColors[category] ?? kMuted;
          final sub = [p['category'], p['supplier']]
              .where((e) => e != null && '$e'.isNotEmpty)
              .join(' · ');
          return GestureDetector(
            // Tap = fiche détail (comparaison fournisseurs + historique), comme
            // le web. Appui long = actions (modifier / supprimer).
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
              builder: (_) =>
                  ProductDetailScreen(productId: '${p['id']}', productName: name),
            )),
            onLongPress: canWrite ? () => _actions(context, ref, p) : null,
            child: MockCard(
            child: Row(
              children: [
                // Pastille d'initiale colorée par famille produit (design).
                Container(
                  width: 40,
                  height: 40,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: chipColor,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    name.isNotEmpty ? name.characters.first.toUpperCase() : '?',
                    style: const TextStyle(
                        color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15),
                  ),
                ),
                const SizedBox(width: 12),
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
          ));
        },
      ),
      floatingActionButton:
          canWrite ? GradientFab(onPressed: () => _create(context, ref)) : null,
    );
  }
}

/// Debounced: without it, typing "beurre" fired six `GET /products/enriched?q=`
/// requests — one per keystroke — on the user's mobile data and the backend.
class _SearchPill extends StatefulWidget {
  const _SearchPill({required this.onChanged});
  final ValueChanged<String> onChanged;

  @override
  State<_SearchPill> createState() => _SearchPillState();
}

class _SearchPillState extends State<_SearchPill> {
  static const _debounce = Duration(milliseconds: 350);
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _onChanged(String value) {
    _timer?.cancel();
    _timer = Timer(_debounce, () => widget.onChanged(value));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: theme.cardColor,
        border: Border.all(color: theme.dividerColor),
        borderRadius: BorderRadius.circular(11),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Row(
        children: [
          const Icon(Icons.search, size: 16, color: kMuted),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              onChanged: _onChanged,
              style: const TextStyle(fontSize: 13),
              decoration: const InputDecoration(
                isCollapsed: true,
                filled: false,
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
