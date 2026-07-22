import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood;

/// Product detail — the mobile equivalent of the web `/produits/[id]` page
/// (`frontend/src/features/products/product-detail.tsx`): supplier price
/// comparison (cheapest flagged) + full purchase history. The mobile list only
/// let you edit/delete; these two endpoints were never called.
final _comparisonProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp =
      await ref.read(apiClientProvider).dio.get('/products/$id/supplier-comparison');
  return Map<String, dynamic>.from(resp.data as Map);
});

final _historyProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/$id/price-history');
  return Map<String, dynamic>.from(resp.data as Map);
});

class ProductDetailScreen extends ConsumerWidget {
  const ProductDetailScreen({super.key, required this.productId, required this.productName});
  final String productId;
  final String productName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final comparison = ref.watch(_comparisonProvider(productId));
    final history = ref.watch(_historyProvider(productId));

    return Scaffold(
      appBar: AppBar(
        title: Text(productName, style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(_comparisonProvider(productId));
          ref.invalidate(_historyProvider(productId));
          await ref.read(_comparisonProvider(productId).future);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
          children: [
            // --- Comparaison fournisseurs ---
            const _SectionTitle('Comparaison fournisseurs'),
            comparison.when(
              loading: () => const _Loading(),
              error: (e, _) => _ErrorLine(apiErrorMessage(e)),
              data: (data) {
                final suppliers = (data['suppliers'] as List? ?? const [])
                    .map((e) => Map<String, dynamic>.from(e as Map))
                    .toList();
                if (suppliers.isEmpty) {
                  return const _EmptyLine('Aucun achat enregistré pour ce produit.');
                }
                return Column(
                  children: [
                    for (final s in suppliers)
                      Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        color: s['is_cheapest'] == true ? const Color(0xFFE9F1E4) : null,
                        child: ListTile(
                          title: Row(
                            children: [
                              Flexible(
                                child: Text(s['supplier_name'] ?? 'Sans fournisseur',
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(fontWeight: FontWeight.w600)),
                              ),
                              if (s['is_cheapest'] == true) ...[
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                      color: const Color(0xFFCFE3C4),
                                      borderRadius: BorderRadius.circular(999)),
                                  child: const Text('Moins cher',
                                      style: TextStyle(
                                          fontSize: 11, fontWeight: FontWeight.w600, color: kGood)),
                                ),
                              ],
                            ],
                          ),
                          subtitle: Text(
                            'Coût standard : ${eur(s['unit_cost_standard'] as num?)}'
                            '${s['unit_code'] != null ? ' / ${s['unit_code']}' : ''}',
                            style: const TextStyle(fontSize: 12.5, color: kMuted),
                          ),
                        ),
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: 12),
            // --- Historique des achats ---
            const _SectionTitle("Historique des achats"),
            history.when(
              loading: () => const _Loading(),
              error: (e, _) => _ErrorLine(apiErrorMessage(e)),
              data: (data) {
                final purchases = (data['purchases'] as List? ?? const [])
                    .map((e) => Map<String, dynamic>.from(e as Map))
                    .toList();
                if (purchases.isEmpty) {
                  return const _EmptyLine('Aucun achat.');
                }
                return Column(
                  children: [
                    for (final p in purchases)
                      Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          title: Text(p['supplier_name'] ?? '—',
                              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                          subtitle: Text(
                            '${p['purchase_date'] ?? ''} · '
                            '${_num(p['qty'])} ${p['unit_code'] ?? ''}',
                            style: const TextStyle(fontSize: 12.5, color: kMuted),
                          ),
                          trailing: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(_money(p['total_price'], p['currency']),
                                  style: const TextStyle(fontWeight: FontWeight.w600)),
                              if (p['variation_pct'] != null)
                                TrendBadge(p['variation_pct'] as num?),
                            ],
                          ),
                        ),
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

String _num(dynamic v) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  if (n == null) return '$v';
  return n == n.roundToDouble() ? '${n.toInt()}' : n.toString().replaceAll('.', ',');
}

String _money(dynamic total, dynamic currency) {
  final t = total is num ? total : num.tryParse('${total ?? ''}');
  if (t == null) return '—';
  if (currency == null || currency == 'EUR' || currency == '€') return eur(t);
  return '${t.toStringAsFixed(2).replaceAll('.', ',')} $currency';
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 4, 4, 8),
        child: Text(text,
            style: const TextStyle(
                fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
      );
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 20),
        child: Center(child: CircularProgressIndicator()),
      );
}

class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Center(child: Text(text, style: const TextStyle(color: kMuted))),
      );
}

class _ErrorLine extends StatelessWidget {
  const _ErrorLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Center(child: Text(text, style: const TextStyle(color: kMuted))),
      );
}
