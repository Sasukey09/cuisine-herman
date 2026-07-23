import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/create_dialog.dart';
import '../../common/edit_delete.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kTerracotta, kProductCategories;
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
              Tab(text: 'Stats'),
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
            _StatsTab(productId: productId),
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
          return const _EmptyLine('Aucun achat enregistré pour ce produit.');
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
// Statistiques
// --------------------------------------------------------------------------- //
class _StatsTab extends ConsumerWidget {
  const _StatsTab({required this.productId});
  final String productId;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(productHistoryProvider(productId));
    final suppliers = ref.watch(productSuppliersProvider(productId));
    final invoices = ref.watch(productInvoicesProvider(productId));
    final recipes = ref.watch(productRecipesProvider(productId));
    return history.when(
      loading: () => const _Loading(),
      error: (e, _) => _ErrorLine(apiErrorMessage(e)),
      data: (data) {
        final purchases = (data['purchases'] as List? ?? const []);
        final costs = purchases
            .map((p) => ((p as Map)['unit_cost_standard'] as num?)?.toDouble())
            .whereType<double>()
            .toList();
        final supCount = (suppliers.valueOrNull?['suppliers'] as List?)?.length ?? 0;
        final invCount = invoices.valueOrNull?.length ?? 0;
        final recCount = recipes.valueOrNull?.length ?? 0;
        if (costs.isEmpty && supCount == 0 && invCount == 0 && recCount == 0) {
          return const _EmptyLine('Pas encore de données pour ce produit.');
        }
        final tiles = <Widget>[
          _tile('Achats', '${costs.length}'),
          _tile('Fournisseurs', '$supCount'),
          _tile('Recettes', '$recCount'),
          _tile('Factures', '$invCount'),
          if (costs.isNotEmpty) _tile('Prix moyen', eur(costs.reduce((a, b) => a + b) / costs.length)),
          if (costs.isNotEmpty) _tile('Minimum', eur(costs.reduce((a, b) => a < b ? a : b))),
          if (costs.isNotEmpty) _tile('Maximum', eur(costs.reduce((a, b) => a > b ? a : b))),
          if (costs.length > 1 && costs.first > 0)
            _tile('Variation', '${((costs.last - costs.first) / costs.first * 100).toStringAsFixed(1)} %'),
        ];
        return Padding(
          padding: const EdgeInsets.all(12),
          child: Wrap(spacing: 8, runSpacing: 8, children: tiles),
        );
      },
    );
  }

  Widget _tile(String k, String v) => Container(
        width: 108,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFFECE4D4)), borderRadius: BorderRadius.circular(12)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(k, style: const TextStyle(fontSize: 11.5, color: kMuted)),
          const SizedBox(height: 4),
          Text(v, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
        ]),
      );
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
