import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../auth/auth_controller.dart';
import '../products/product_detail_screen.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad, kTerracotta;
import 'quotes_screen.dart' show quoteProductsProvider, statusOf;

/// Détail d'un devis : panier + comparaison des fournisseurs + conversion en
/// commande (parité avec `/devis/[id]` du web). Le comparateur chiffre le panier
/// par fournisseur à partir des derniers prix connus.
final quoteProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/quotes/$id');
  return Map<String, dynamic>.from(resp.data as Map);
});

final quoteComparisonProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/quotes/$id/comparison');
  return Map<String, dynamic>.from(resp.data as Map);
});

String _num(dynamic v) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  if (n == null) return '$v';
  return n == n.roundToDouble() ? '${n.toInt()}' : n.toString().replaceAll('.', ',');
}

class QuoteDetailScreen extends ConsumerWidget {
  const QuoteDetailScreen({super.key, required this.quoteId, this.reference});
  final String quoteId;
  final String? reference;

  Future<void> _reload(WidgetRef ref) async {
    ref.invalidate(quoteProvider(quoteId));
    ref.invalidate(quoteComparisonProvider(quoteId));
    await ref.read(quoteProvider(quoteId).future);
  }

  Future<void> _addLine(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final products = await ref.read(quoteProductsProvider.future);
    if (!context.mounted) return;
    final fields = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _AddLineDialog(products: products),
    );
    if (fields == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/quotes/$quoteId/lines', data: fields);
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Ligne ajoutée.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _deleteLine(BuildContext context, WidgetRef ref, String lineId) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(apiClientProvider).dio.delete('/quotes/$quoteId/lines/$lineId');
      await _reload(ref);
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _order(BuildContext context, WidgetRef ref, String supplierId,
      String? supplierName) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(apiClientProvider).dio.post('/quotes/$quoteId/order',
          data: {'supplier_id': supplierId});
      await _reload(ref);
      messenger.showSnackBar(SnackBar(
          content: Text('Commande passée${supplierName != null ? ' chez $supplierName' : ''}.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _delete(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Supprimer ce devis ?'),
        content: const Text('Le devis et ses lignes seront supprimés. Action irréversible.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: kBad),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Supprimer')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(apiClientProvider).dio.delete('/quotes/$quoteId');
      messenger.showSnackBar(const SnackBar(content: Text('Devis supprimé.')));
      navigator.pop(true);
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canWrite = ref.watch(canWriteProvider);
    final quoteAsync = ref.watch(quoteProvider(quoteId));

    final title = quoteAsync.valueOrNull?['reference'] as String? ?? reference ?? 'Devis';
    return Scaffold(
      appBar: AppBar(
        title: Text(title, style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      body: RefreshIndicator(
        onRefresh: () => _reload(ref),
        child: quoteAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Center(child: Text(apiErrorMessage(e))),
            ),
          ]),
          data: (quote) {
            final isDraft = (quote['status'] ?? 'draft') == 'draft';
            final lines = (quote['lines'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
            final st = statusOf(quote['status'] as String?);
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
              children: [
                _headerCard(context, ref, quote, st, canWrite && isDraft),
                const SizedBox(height: 16),
                _basketCard(context, ref, lines, canWrite && isDraft),
                const SizedBox(height: 16),
                _ComparisonCard(
                  quoteId: quoteId,
                  canOrder: canWrite && isDraft,
                  onOrder: (sid, sname) => _order(context, ref, sid, sname),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _headerCard(BuildContext context, WidgetRef ref, Map<String, dynamic> quote,
      ({String label, Color bg, Color fg}) st, bool canDelete) {
    final title = (quote['title'] as String?)?.trim();
    final total = quote['total_amount'] as num?;
    final supplierName = quote['supplier_name'] as String?;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title?.isNotEmpty == true ? title! : '${quote['reference'] ?? 'Devis'}',
                    style: const TextStyle(
                        fontFamily: 'Newsreader', fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                  decoration:
                      BoxDecoration(color: st.bg, borderRadius: BorderRadius.circular(999)),
                  child: Text(st.label,
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: st.fg)),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              [
                '${quote['reference'] ?? ''}',
                if (supplierName != null) 'Commandé chez $supplierName',
                if (total != null) eur(total),
              ].where((s) => s.isNotEmpty).join('  ·  '),
              style: const TextStyle(fontSize: 13, color: kMuted),
            ),
            if (canDelete) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(foregroundColor: kBad),
                onPressed: () => _delete(context, ref),
                icon: const Icon(Icons.delete_outline, size: 18),
                label: const Text('Supprimer'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _basketCard(BuildContext context, WidgetRef ref, List<Map<String, dynamic>> lines,
      bool canWrite) {
    final showPrice = lines.any((l) => l['unit_price'] != null);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Panier',
                style: TextStyle(
                    fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
            const Text('Les produits à sourcer et leurs quantités.',
                style: TextStyle(fontSize: 12, color: kMuted)),
            const SizedBox(height: 10),
            if (lines.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 10),
                child: Text('Aucune ligne.', style: TextStyle(color: kMuted)),
              )
            else
              for (final l in lines)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      Expanded(
                        child: InkWell(
                          onTap: l['product_id'] != null
                              ? () => Navigator.of(context).push(MaterialPageRoute(
                                    builder: (_) => ProductDetailScreen(
                                      productId: '${l['product_id']}',
                                      productName: '${l['product_name'] ?? 'Produit'}',
                                    ),
                                  ))
                              : null,
                          child: Text(
                            '${l['product_name'] ?? l['description'] ?? '—'}',
                            style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w500),
                          ),
                        ),
                      ),
                      Text('× ${_num(l['qty'])}',
                          style: const TextStyle(fontSize: 13, color: kMuted)),
                      if (showPrice) ...[
                        const SizedBox(width: 10),
                        SizedBox(
                          width: 70,
                          child: Text(
                            l['unit_price'] != null ? eur(l['unit_price'] as num?) : '—',
                            textAlign: TextAlign.right,
                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                      if (canWrite)
                        IconButton(
                          icon: const Icon(Icons.delete_outline, size: 19),
                          visualDensity: VisualDensity.compact,
                          onPressed: () => _deleteLine(context, ref, '${l['id']}'),
                        ),
                    ],
                  ),
                ),
            if (canWrite) ...[
              const Divider(height: 20),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => _addLine(context, ref),
                  icon: const Icon(Icons.add, size: 18, color: kTerracotta),
                  label: const Text('Ajouter un produit'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Tableau comparatif des fournisseurs pour le panier.
class _ComparisonCard extends ConsumerWidget {
  const _ComparisonCard({
    required this.quoteId,
    required this.canOrder,
    required this.onOrder,
  });
  final String quoteId;
  final bool canOrder;
  final void Function(String supplierId, String? supplierName) onOrder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final compAsync = ref.watch(quoteComparisonProvider(quoteId));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Comparaison des fournisseurs',
                style: TextStyle(
                    fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
            const Text('Coût du panier par fournisseur, à partir des derniers prix connus.',
                style: TextStyle(fontSize: 12, color: kMuted)),
            const SizedBox(height: 12),
            compAsync.when(
              loading: () => const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (e, _) => Text(apiErrorMessage(e), style: const TextStyle(color: kMuted)),
              data: (comp) {
                final suppliers =
                    (comp['suppliers'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
                final priceable = comp['priceable_count'] as int? ?? 0;
                if (suppliers.isEmpty) {
                  return const Text(
                    'Aucun fournisseur ne peut chiffrer ce panier. Ajoutez des prix '
                    '(via une facture) ou associez des fournisseurs aux produits.',
                    style: TextStyle(fontSize: 13, color: kMuted),
                  );
                }
                return Column(
                  children: [
                    for (final s in suppliers)
                      _supplierRow(s, priceable),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _supplierRow(Map<String, dynamic> s, int priceable) {
    final total = s['total'] as num?;
    final fullCoverage = s['is_full_coverage'] == true;
    final cheapest = s['is_cheapest'] == true;
    final covered = s['covered_count'] as int? ?? 0;
    final lead = s['max_lead_time_days'] as int?;
    final name = s['supplier_name'] as String? ?? 'Fournisseur';
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: cheapest ? const Color(0xFFF0F5EC) : null,
        border: Border.all(color: const Color(0x22000000)),
        borderRadius: BorderRadius.circular(11),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(name,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              ),
              Text(eur(total),
                  style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              if (cheapest) _chip('Moins cher', kGood, const Color(0xFFE3ECDB)),
              if (s['preferred'] == true) _chip('Préféré', kTerracotta, const Color(0xFFEFE1D3)),
              if (!cheapest && s['is_best_coverage'] == true && !fullCoverage)
                _chip('Meilleure couverture', kWarn, const Color(0xFFF6EAD4)),
              _meta(fullCoverage ? 'Couverture complète' : 'Couverture $covered/$priceable',
                  fullCoverage ? kGood : kWarn),
              if (lead != null) _meta('Délai $lead j', kMuted),
            ],
          ),
          if (canOrder) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: cheapest ? kTerracotta : null,
                  visualDensity: VisualDensity.compact,
                ),
                onPressed: () => onOrder('${s['supplier_id']}', s['supplier_name'] as String?),
                child: const Text('Commander'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _chip(String label, Color fg, Color bg) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
        child: Text(label,
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: fg)),
      );

  Widget _meta(String label, Color color) =>
      Text(label, style: TextStyle(fontSize: 12, color: color));
}

/// Ajout d'une ligne au panier : produit + quantité.
class _AddLineDialog extends StatefulWidget {
  const _AddLineDialog({required this.products});
  final List<dynamic> products;

  @override
  State<_AddLineDialog> createState() => _AddLineDialogState();
}

class _AddLineDialogState extends State<_AddLineDialog> {
  String? _productId;
  final _qty = TextEditingController();

  @override
  void dispose() {
    _qty.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Ajouter un produit'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            // ignore: deprecated_member_use
            value: _productId,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Produit'),
            items: [
              for (final p in widget.products)
                DropdownMenuItem(
                  value: '${p['id']}',
                  child: Text('${p['name'] ?? ''}',
                      maxLines: 1, overflow: TextOverflow.ellipsis),
                ),
            ],
            onChanged: (v) => setState(() => _productId = v),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _qty,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Quantité'),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            if (_productId == null) return;
            Navigator.pop(context, {
              'product_id': _productId,
              'qty': _qty.text.trim().isEmpty
                  ? null
                  : double.tryParse(_qty.text.replaceAll(',', '.')),
            });
          },
          child: const Text('Ajouter'),
        ),
      ],
    );
  }
}
