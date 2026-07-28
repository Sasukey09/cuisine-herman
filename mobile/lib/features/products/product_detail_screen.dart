import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/create_dialog.dart';
import '../../common/edit_delete.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import 'product_quote_history.dart';
import '../../main.dart' show kMuted, kGood, kBad, kTerracotta, kProductCategories;
import '../auth/auth_controller.dart';
import '../invoices/invoice_detail_screen.dart';
import '../recipes/recipe_detail_screen.dart';

/// Product detail — the mobile equivalent of the web `/produits/[id]` page, with
/// the same six tabs: Informations, Fournisseurs, Historique des prix, Factures,
/// Recettes, Statistiques.
final productDetailProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/$id');
  return Map<String, dynamic>.from(resp.data as Map);
});

final productSuppliersProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/$id/suppliers');
  return Map<String, dynamic>.from(resp.data as Map);
});

final productHistoryProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/$id/price-history');
  return Map<String, dynamic>.from(resp.data as Map);
});

final productInvoicesProvider =
    FutureProvider.autoDispose.family<List<dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/$id/invoices');
  return (resp.data as Map)['invoices'] as List? ?? const [];
});

final productRecipesProvider =
    FutureProvider.autoDispose.family<List<dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/$id/recipes');
  return (resp.data as Map)['recipes'] as List? ?? const [];
});

/// La fiche 360° du produit (§ Achats) — miroir de `_supplierOverviewProvider`
/// dans `supplier_detail_screen.dart`.
final _productOverviewProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/$id/overview');
  return Map<String, dynamic>.from(resp.data as Map);
});

final _allSuppliersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/', queryParameters: {'limit': 200});
  return resp.data as List? ?? const [];
});

class ProductDetailScreen extends ConsumerWidget {
  const ProductDetailScreen({super.key, required this.productId, required this.productName});
  final String productId;
  final String productName;

  void _refresh(WidgetRef ref) {
    ref.invalidate(productDetailProvider(productId));
    ref.invalidate(productSuppliersProvider(productId));
    ref.invalidate(productHistoryProvider(productId));
    ref.invalidate(productInvoicesProvider(productId));
    ref.invalidate(productRecipesProvider(productId));
    ref.invalidate(_productOverviewProvider(productId));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 6,
      child: Scaffold(
        appBar: AppBar(
          title: Text(productName, style: const TextStyle(fontFamily: 'Newsreader')),
          bottom: const TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: [
              Tab(text: 'Infos'),
              Tab(text: 'Fournisseurs'),
              Tab(text: 'Prix'),
              Tab(text: 'Factures'),
              Tab(text: 'Recettes'),
              Tab(text: "Vue d'ensemble"),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _InfosTab(productId: productId),
            _SuppliersTab(productId: productId, onChanged: () => _refresh(ref)),
            _PricesTab(productId: productId),
            _InvoicesTab(productId: productId),
            _RecipesTab(productId: productId),
            _OverviewTab(productId: productId),
          ],
        ),
      ),
    );
  }
}

// --------------------------------------------------------------------------- //
// Informations
// --------------------------------------------------------------------------- //
class _InfosTab extends ConsumerWidget {
  const _InfosTab({required this.productId});
  final String productId;

  Future<void> _edit(BuildContext context, WidgetRef ref, Map<String, dynamic> p) async {
    final messenger = ScaffoldMessenger.of(context);
    final data = await showEditDialog(
      context,
      title: 'Modifier le produit',
      fields: const [
        CreateField('name', 'Nom', required: true),
        CreateField('sku', 'SKU (optionnel)'),
        CreateField('category', 'Catégorie',
            options: kProductCategories, emptyLabel: 'Automatique (selon le nom)'),
        CreateField('vat_rate', 'TVA (%)', keyboard: TextInputType.number),
      ],
      initial: {
        'name': '${p['name'] ?? ''}',
        'sku': '${p['sku'] ?? ''}',
        'category': '${p['category'] ?? ''}',
        'vat_rate': p['vat_rate'] != null ? '${p['vat_rate']}' : '',
      },
    );
    if (data == null) return;
    await updateEntity(
      ref,
      messenger,
      path: '/products/$productId',
      body: {
        'name': data['name'],
        'sku': (data['sku'] ?? '').isEmpty ? null : data['sku'],
        'category': (data['category'] ?? '').isEmpty ? null : data['category'],
        'vat_rate': (data['vat_rate'] ?? '').isEmpty ? null : double.tryParse(data['vat_rate']!),
      },
      successMessage: 'Produit modifié.',
      onDone: () => ref.invalidate(productDetailProvider(productId)),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canWrite = ref.watch(canWriteProvider);
    final async = ref.watch(productDetailProvider(productId));
    return async.when(
      loading: () => const _Loading(),
      error: (e, _) => _ErrorLine(apiErrorMessage(e)),
      data: (p) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _kv('Nom', '${p['name'] ?? '—'}'),
          _kv('Référence / SKU', '${p['sku'] ?? '—'}'),
          _kv('Catégorie', '${p['category'] ?? 'Non classé'}'),
          _kv('Unité de base', '${p['unit'] ?? '—'}'),
          _kv('TVA', p['vat_rate'] != null ? '${p['vat_rate']} %' : '—'),
          if (canWrite) ...[
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => _edit(context, ref, p),
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('Modifier'),
            ),
          ],
        ],
      ),
    );
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(k, style: const TextStyle(fontSize: 12, color: kMuted)),
            const SizedBox(height: 2),
            Text(v, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          ],
        ),
      );
}

// --------------------------------------------------------------------------- //
// Fournisseurs (+ CRUD)
// --------------------------------------------------------------------------- //
class _SuppliersTab extends ConsumerWidget {
  const _SuppliersTab({required this.productId, required this.onChanged});
  final String productId;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canWrite = ref.watch(canWriteProvider);
    final async = ref.watch(productSuppliersProvider(productId));
    return Scaffold(
      body: async.when(
        loading: () => const _Loading(),
        error: (e, _) => _ErrorLine(apiErrorMessage(e)),
        data: (data) {
          final suppliers = (data['suppliers'] as List? ?? const [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          if (suppliers.isEmpty) {
            return const _EmptyLine('Aucun fournisseur pour ce produit.\nAjoutez-en un ou importez une facture.');
          }
          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              for (final s in suppliers) _supplierCard(context, ref, s, canWrite),
            ],
          );
        },
      ),
      floatingActionButton: canWrite
          ? FloatingActionButton.extended(
              onPressed: () => _openDialog(context, ref, null),
              backgroundColor: kTerracotta,
              icon: const Icon(Icons.add),
              label: const Text('Fournisseur'),
            )
          : null,
    );
  }

  Widget _supplierCard(BuildContext context, WidgetRef ref, Map<String, dynamic> s, bool canWrite) {
    final preferred = s['preferred'] == true;
    final available = s['available'] != false;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      color: preferred ? const Color(0xFFF6EAD4) : null,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 6, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (preferred) const Icon(Icons.star, size: 16, color: Color(0xFFD9A441)),
                if (preferred) const SizedBox(width: 4),
                Expanded(
                  child: Text(s['supplier_name'] ?? 'Sans fournisseur',
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5)),
                ),
                if (s['is_cheapest'] == true)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                        color: const Color(0xFFCFE3C4), borderRadius: BorderRadius.circular(999)),
                    child: const Text('Moins cher',
                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: kGood)),
                  ),
                if (canWrite)
                  PopupMenuButton<String>(
                    onSelected: (v) async {
                      if (v == 'edit') {
                        _openDialog(context, ref, s);
                      } else if (v == 'preferred') {
                        await _setPreferred(context, ref, s);
                      } else if (v == 'delete') {
                        await _delete(ref, context, s);
                      }
                    },
                    itemBuilder: (_) => [
                      if (!preferred) const PopupMenuItem(value: 'preferred', child: Text('Définir préféré')),
                      const PopupMenuItem(value: 'edit', child: Text('Modifier')),
                      // A supplier that only appears via purchases has no catalog
                      // link to remove.
                      if (s['link_id'] != null)
                        const PopupMenuItem(value: 'delete', child: Text('Retirer')),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Wrap(spacing: 14, runSpacing: 4, children: [
              _chip(available ? Icons.check_circle : Icons.cancel_outlined,
                  available ? 'Disponible' : 'Indispo.', available ? kGood : kMuted),
              if (s['supplier_sku'] != null) _chip(Icons.qr_code, 'Réf ${s['supplier_sku']}', kMuted),
              if (s['lead_time_days'] != null) _chip(Icons.schedule, 'Délai ${s['lead_time_days']} j', kMuted),
            ]),
            const SizedBox(height: 6),
            Wrap(spacing: 14, runSpacing: 2, children: [
              if (s['last_cost'] != null) _price('Dernier', s['last_cost'], s['unit_code']),
              if (s['avg_cost'] != null) _price('Moyen', s['avg_cost'], null),
              if (s['best_cost'] != null) _price('Meilleur', s['best_cost'], null),
              if (s['last_purchase_date'] != null)
                Text('Dernier achat : ${s['last_purchase_date']}',
                    style: const TextStyle(fontSize: 11.5, color: kMuted)),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _chip(IconData i, String t, Color c) => Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(i, size: 14, color: c),
        const SizedBox(width: 3),
        Text(t, style: TextStyle(fontSize: 12, color: c)),
      ]);

  Widget _price(String label, dynamic v, dynamic unit) => Text(
        '$label ${eur(v as num?)}${unit != null ? '/$unit' : ''}',
        style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
      );

  /// Set a supplier as preferred. If it only appears via purchases (no catalog
  /// link yet), CREATE the link (idempotent POST) instead of patching a link
  /// that does not exist.
  Future<void> _setPreferred(BuildContext context, WidgetRef ref, Map<String, dynamic> s) async {
    final messenger = ScaffoldMessenger.of(context);
    final dio = ref.read(apiClientProvider).dio;
    try {
      if (s['link_id'] != null) {
        await dio.patch('/products/$productId/suppliers/${s['link_id']}', data: {'preferred': true});
      } else {
        await dio.post('/products/$productId/suppliers',
            data: {'supplier_id': s['supplier_id'], 'preferred': true});
      }
      messenger.showSnackBar(const SnackBar(content: Text('Fournisseur défini comme préféré.')));
      onChanged();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _delete(WidgetRef ref, BuildContext context, Map<String, dynamic> s) async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Retirer ce fournisseur ?'),
        content: Text('« ${s['supplier_name']} » sera retiré de ce produit. Les prix relevés sont conservés.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Retirer')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(apiClientProvider).dio.delete('/products/$productId/suppliers/${s['link_id']}');
      messenger.showSnackBar(const SnackBar(content: Text('Fournisseur retiré.')));
      onChanged();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _openDialog(BuildContext context, WidgetRef ref, Map<String, dynamic>? existing) async {
    final messenger = ScaffoldMessenger.of(context);
    final dio = ref.read(apiClientProvider).dio;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _SupplierDialog(productId: productId, existing: existing),
    );
    if (result == null) return;
    final linkId = existing?['link_id'];
    try {
      if (linkId != null) {
        await dio.patch('/products/$productId/suppliers/$linkId', data: result);
      } else {
        // Add, or upsert a purchase-only supplier into the catalog.
        final sid = result['supplier_id'] ?? existing?['supplier_id'];
        await dio.post('/products/$productId/suppliers', data: {...result, 'supplier_id': sid});
      }
      messenger.showSnackBar(SnackBar(content: Text(linkId != null ? 'Fournisseur mis à jour.' : 'Fournisseur associé.')));
      onChanged();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }
}

/// Add/edit a supplier link. Returns the body to POST/PATCH, or null.
class _SupplierDialog extends ConsumerStatefulWidget {
  const _SupplierDialog({required this.productId, this.existing});
  final String productId;
  final Map<String, dynamic>? existing;
  @override
  ConsumerState<_SupplierDialog> createState() => _SupplierDialogState();
}

class _SupplierDialogState extends ConsumerState<_SupplierDialog> {
  String? _supplierId;
  final _sku = TextEditingController();
  final _lead = TextEditingController();
  bool _available = true;
  bool _preferred = false;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    if (e != null) {
      _supplierId = '${e['supplier_id']}';
      _sku.text = '${e['supplier_sku'] ?? ''}';
      _lead.text = e['lead_time_days'] != null ? '${e['lead_time_days']}' : '';
      _available = e['available'] != false;
      _preferred = e['preferred'] == true;
    }
  }

  @override
  void dispose() {
    _sku.dispose();
    _lead.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.existing != null;
    final suppliers = ref.watch(_allSuppliersProvider);
    return AlertDialog(
      title: Text(isEdit ? 'Modifier le fournisseur' : 'Associer un fournisseur'),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (!isEdit)
            suppliers.when(
              loading: () => const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator()),
              error: (e, _) => Text(apiErrorMessage(e)),
              data: (list) => DropdownButtonFormField<String>(
                initialValue: _supplierId,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Fournisseur'),
                items: [
                  for (final s in list)
                    DropdownMenuItem(value: '${(s as Map)['id']}', child: Text('${s['name']}')),
                ],
                onChanged: (v) => setState(() => _supplierId = v),
              ),
            ),
          TextField(controller: _sku, decoration: const InputDecoration(labelText: 'Référence fournisseur')),
          TextField(
            controller: _lead,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Délai de livraison (jours)'),
          ),
          const SizedBox(height: 8),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _available,
            title: const Text('Disponible'),
            onChanged: (v) => setState(() => _available = v ?? true),
          ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _preferred,
            title: const Text('Fournisseur préféré'),
            onChanged: (v) => setState(() => _preferred = v ?? false),
          ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: (!isEdit && _supplierId == null)
              ? null
              : () {
                  final body = <String, dynamic>{
                    if (!isEdit) 'supplier_id': _supplierId,
                    'supplier_sku': _sku.text.trim().isEmpty ? null : _sku.text.trim(),
                    'lead_time_days': _lead.text.trim().isEmpty ? null : int.tryParse(_lead.text.trim()),
                    'available': _available,
                    'preferred': _preferred,
                  };
                  Navigator.pop(context, body);
                },
          child: Text(isEdit ? 'Enregistrer' : 'Associer'),
        ),
      ],
    );
  }
}

// --------------------------------------------------------------------------- //
// Historique des prix (stats + sparkline + list)
// --------------------------------------------------------------------------- //
class _PricesTab extends ConsumerWidget {
  const _PricesTab({required this.productId});
  final String productId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(productHistoryProvider(productId));
    return async.when(
      loading: () => const _Loading(),
      error: (e, _) => _ErrorLine(apiErrorMessage(e)),
      data: (data) {
        final purchases = (data['purchases'] as List? ?? const [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        final costs = purchases
            .map((p) => (p['unit_cost_standard'] as num?)?.toDouble())
            .whereType<double>()
            .toList();
        if (purchases.isEmpty) {
          // Aucun achat ne veut pas dire aucune information : les devis reçus
          // pour ce produit restent à afficher.
          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              const _EmptyLine('Aucun achat enregistré pour ce produit.'),
              ProductQuoteHistorySection(productId: productId),
            ],
          );
        }
        final unit = purchases.isNotEmpty ? purchases.first['unit_code'] : null;
        return ListView(
          padding: const EdgeInsets.all(12),
          children: [
            if (costs.isNotEmpty)
              Wrap(spacing: 8, runSpacing: 8, children: [
                _stat('Dernier', '${eur(costs.last)}${unit != null ? '/$unit' : ''}'),
                _stat('Moyen', eur(costs.reduce((a, b) => a + b) / costs.length)),
                _stat('Minimum', eur(costs.reduce((a, b) => a < b ? a : b))),
                _stat('Maximum', eur(costs.reduce((a, b) => a > b ? a : b))),
              ]),
            if (costs.length > 1) ...[
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('Évolution du coût standardisé',
                        style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                    const SizedBox(height: 8),
                    SizedBox(height: 80, child: CustomPaint(size: Size.infinite, painter: _Sparkline(costs))),
                  ]),
                ),
              ),
            ],
            const SizedBox(height: 12),
            const _SectionTitle('Historique des achats'),
            for (final p in purchases)
              Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  title: Text(p['supplier_name'] ?? '—',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                  subtitle: Text('${p['purchase_date'] ?? ''} · ${_num(p['qty'])} ${p['unit_code'] ?? ''}',
                      style: const TextStyle(fontSize: 12.5, color: kMuted)),
                  trailing: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(_money(p['total_price'], p['currency']),
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      if (p['variation_pct'] != null) TrendBadge(p['variation_pct'] as num?),
                    ],
                  ),
                ),
              ),
            // « Proposé » se lit juste sous « payé » : c'est la comparaison
            // des deux qui a de la valeur.
            ProductQuoteHistorySection(productId: productId),
          ],
        );
      },
    );
  }

  Widget _stat(String k, String v) => Container(
        width: 150,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFFECE4D4)), borderRadius: BorderRadius.circular(10)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(k, style: const TextStyle(fontSize: 11.5, color: kMuted)),
          const SizedBox(height: 2),
          Text(v, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        ]),
      );
}

class _Sparkline extends CustomPainter {
  _Sparkline(this.values);
  final List<double> values;
  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    final lo = values.reduce((a, b) => a < b ? a : b);
    final hi = values.reduce((a, b) => a > b ? a : b);
    final span = (hi - lo).abs() < 1e-9 ? 1.0 : hi - lo;
    final dx = size.width / (values.length - 1);
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = dx * i;
      final y = size.height - ((values[i] - lo) / span) * size.height;
      i == 0 ? path.moveTo(x, y) : path.lineTo(x, y);
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = kTerracotta
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant _Sparkline old) => old.values != values;
}

// --------------------------------------------------------------------------- //
// Factures
// --------------------------------------------------------------------------- //
class _InvoicesTab extends ConsumerWidget {
  const _InvoicesTab({required this.productId});
  final String productId;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(productInvoicesProvider(productId));
    return async.when(
      loading: () => const _Loading(),
      error: (e, _) => _ErrorLine(apiErrorMessage(e)),
      data: (invoices) {
        if (invoices.isEmpty) return const _EmptyLine('Aucune facture pour ce produit.');
        return ListView(
          padding: const EdgeInsets.all(12),
          children: [
            for (final raw in invoices)
              Builder(builder: (context) {
                final inv = Map<String, dynamic>.from(raw as Map);
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    title: Text('${inv['invoice_number'] ?? 'Facture'}',
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text('${inv['date'] ?? ''} · ${inv['supplier_name'] ?? '—'} · '
                        '${_num(inv['qty'])} · ${_money(inv['line_total'], inv['currency'])}',
                        style: const TextStyle(fontSize: 12.5, color: kMuted)),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => InvoiceDetailScreen(
                          invoiceId: '${inv['invoice_id']}', invoiceNumber: '${inv['invoice_number'] ?? ''}'),
                    )),
                  ),
                );
              }),
          ],
        );
      },
    );
  }
}

// --------------------------------------------------------------------------- //
// Recettes
// --------------------------------------------------------------------------- //
class _RecipesTab extends ConsumerWidget {
  const _RecipesTab({required this.productId});
  final String productId;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(productRecipesProvider(productId));
    return async.when(
      loading: () => const _Loading(),
      error: (e, _) => _ErrorLine(apiErrorMessage(e)),
      data: (recipes) {
        if (recipes.isEmpty) return const _EmptyLine('Aucune recette n\'utilise ce produit.');
        return ListView(
          padding: const EdgeInsets.all(12),
          children: [
            for (final raw in recipes)
              Builder(builder: (context) {
                final r = Map<String, dynamic>.from(raw as Map);
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    title: Text('${r['name'] ?? '—'}', style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: r['qty'] != null
                        ? Text('${_num(r['qty'])} ${r['unit'] ?? ''}',
                            style: const TextStyle(fontSize: 12.5, color: kMuted))
                        : null,
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => RecipeDetailScreen(recipeId: '${r['recipe_id']}', recipeName: '${r['name'] ?? ''}'),
                    )),
                  ),
                );
              }),
          ],
        );
      },
    );
  }
}

// --------------------------------------------------------------------------- //
// Vue d'ensemble (fiche 360°, server-fed — miroir de `_Scorecard` fournisseur)
// --------------------------------------------------------------------------- //
class _OverviewTab extends ConsumerWidget {
  const _OverviewTab({required this.productId});
  final String productId;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final overview = ref.watch(_productOverviewProvider(productId));
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        overview.maybeWhen(orElse: () => const SizedBox.shrink(), data: (o) => _Scorecard(o)),
      ],
    );
  }
}

/// La fiche produit 360° : ce que ce produit coûte, chez qui, et ce que la
/// mise en concurrence a fait gagner. Miroir de `_Scorecard` (fournisseur)
/// dans `supplier_detail_screen.dart` — mêmes tuiles/barres/listes, mais
/// centré sur le produit plutôt que sur le fournisseur. Les champs nullable
/// (pas encore de fournisseur le moins cher, pas d'offre récente…) s'affichent
/// « — », jamais une valeur inventée.
class _Scorecard extends StatelessWidget {
  const _Scorecard(this.o);
  final Map<String, dynamic> o;

  @override
  Widget build(BuildContext context) {
    final trend = o['price_trend_pct'] as num?;
    final monthly = (o['monthly'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final topSuppliers = (o['top_suppliers'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final savings = o['savings'] as Map?;
    final cheapest = o['cheapest_supplier'] as Map?;
    final offers = o['offers'] as Map?;
    final trendColor = trend == null ? kMuted : (trend > 0 ? kBad : kGood);

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: _tile(eur(o['annual_amount'] as num?), 'Payé sur 12 mois', kTerracotta)),
        const SizedBox(width: 8),
        Expanded(
          child: _tile(
            trend == null
                ? '—'
                : '${trend > 0 ? '+' : ''}${trend.toStringAsFixed(1).replaceAll('.', ',')} %',
            'Inflation produit',
            trendColor,
          ),
        ),
      ]),
      if (savings != null && ((savings['compared_lines'] as num?) ?? 0) > 0) ...[
        const SizedBox(height: 8),
        _savingsTile(Map<String, dynamic>.from(savings)),
      ],
      const SizedBox(height: 8),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Wrap(spacing: 14, runSpacing: 4, children: [
            _count('${o['purchase_count'] ?? 0}', 'achats'),
            _count('${o['supplier_count'] ?? 0}', 'fournisseurs'),
            _count('${o['recipe_count'] ?? 0}', 'recettes'),
            _count('${o['offer_count'] ?? 0}', 'offres'),
          ]),
        ),
      ),
      if (monthly.length > 1) ...[
        const SizedBox(height: 8),
        _MonthlyBars(monthly),
      ],
      const SizedBox(height: 8),
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: _cheapestCard(cheapest)),
        const SizedBox(width: 8),
        Expanded(child: _offersCard(offers)),
      ]),
      if (topSuppliers.isNotEmpty) ...[
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Fournisseurs',
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: kMuted)),
              const SizedBox(height: 6),
              for (final s in topSuppliers.take(6))
                Padding(
                  padding: const EdgeInsets.only(bottom: 3),
                  child: Row(children: [
                    Expanded(
                      child: Row(children: [
                        Flexible(
                          child: Text('${s['supplier_name'] ?? 'Fournisseur'}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13)),
                        ),
                        if (s['is_cheapest'] == true) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                                color: const Color(0xFFCFE3C4), borderRadius: BorderRadius.circular(999)),
                            child: const Text('Moins cher',
                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: kGood)),
                          ),
                        ],
                      ]),
                    ),
                    Text(eur(s['amount'] as num?),
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  ]),
                ),
            ]),
          ),
        ),
      ],
    ]);
  }

  Widget _tile(String value, String label, Color color) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: color)),
            const SizedBox(height: 2),
            Text(label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 11, color: kMuted)),
          ]),
        ),
      );

  Widget _savingsTile(Map<String, dynamic> s) {
    final labels = Map<String, dynamic>.from(s['labels'] as Map? ?? const {});
    final rate = s['best_choice_rate'] as num?;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(eur(s['realized'] as num?),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: kGood)),
          const SizedBox(height: 2),
          Text('${labels['realized'] ?? 'Économisé'}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11, color: kMuted)),
          if (rate != null) ...[
            const SizedBox(height: 2),
            Text(
                '${labels['best_choice_rate'] ?? 'Taux de meilleur choix'} · ${(rate * 100).round()} %',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 10.5, color: kMuted)),
          ],
        ]),
      ),
    );
  }

  Widget _count(String n, String label) => RichText(
        text: TextSpan(children: [
          TextSpan(
              text: '$n ',
              style: const TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF2B2B2B))),
          TextSpan(text: label, style: const TextStyle(fontSize: 13, color: kMuted)),
        ]),
      );

  Widget _cheapestCard(Map? cheapest) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Moins cher',
                style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: kMuted)),
            const SizedBox(height: 6),
            if (cheapest == null)
              const Text('—', style: TextStyle(fontSize: 13, color: kMuted))
            else
              Row(children: [
                Expanded(
                  child: Text('${cheapest['supplier_name'] ?? 'Fournisseur'}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13)),
                ),
                Text(eur(cheapest['cost'] as num?),
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              ]),
          ]),
        ),
      );

  Widget _offersCard(Map? offers) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Offres',
                style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: kMuted)),
            const SizedBox(height: 6),
            if (offers == null)
              const Text('—', style: TextStyle(fontSize: 13, color: kMuted))
            else ...[
              _offerLine(
                  'Meilleure${offers['best_supplier_name'] != null ? ' · ${offers['best_supplier_name']}' : ''}',
                  eur(offers['best_price'] as num?)),
              _offerLine('Dernière', eur(offers['latest_price'] as num?)),
              _offerLine(
                  'Moyenne · ${offers['supplier_count'] ?? 0} fourn.', eur(offers['avg_price'] as num?)),
            ],
          ]),
        ),
      );

  Widget _offerLine(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 3),
        child: Row(children: [
          Expanded(
            child: Text(label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: kMuted)),
          ),
          Text(value, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
        ]),
      );
}

class _MonthlyBars extends StatelessWidget {
  const _MonthlyBars(this.monthly);
  final List<Map<String, dynamic>> monthly;

  @override
  Widget build(BuildContext context) {
    final max = monthly
        .map((m) => (m['amount'] as num?)?.toDouble() ?? 0)
        .fold<double>(1, (a, b) => b > a ? b : a);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Dépense mensuelle',
              style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: kMuted)),
          const SizedBox(height: 8),
          SizedBox(
            height: 76,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (final m in monthly)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 2),
                      child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                        Container(
                          height:
                              (((m['amount'] as num?)?.toDouble() ?? 0) / max * 58).clamp(2, 58),
                          decoration: BoxDecoration(
                            color: kTerracotta.withValues(alpha: 0.7),
                            borderRadius: const BorderRadius.vertical(top: Radius.circular(3)),
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text('${m['month']}'.substring(5),
                            style: const TextStyle(fontSize: 8, color: kMuted)),
                      ]),
                    ),
                  ),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}

// --------------------------------------------------------------------------- //
// Shared helpers
// --------------------------------------------------------------------------- //
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
            style: const TextStyle(fontFamily: 'Newsreader', fontSize: 16, fontWeight: FontWeight.w700)),
      );
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) =>
      const Padding(padding: EdgeInsets.symmetric(vertical: 30), child: Center(child: CircularProgressIndicator()));
}

class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(28),
        child: Center(child: Text(text, textAlign: TextAlign.center, style: const TextStyle(color: kMuted))),
      );
}

class _ErrorLine extends StatelessWidget {
  const _ErrorLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(20),
        child: Center(child: Text(text, textAlign: TextAlign.center, style: const TextStyle(color: kMuted))),
      );
}
