import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kBad, kWarn, kTerracotta;

/// Recipe detail + ingredient management — the mobile equivalent of the web
/// recipe page. The recipes list only let you set name/portions/price; there was
/// no way to add a first ingredient, come back and add a second, edit or remove
/// one. This screen does all of it, on top of the same version-based backend:
/// every change saves a new version (POST /recipes/{id}/versions) and the cost
/// per portion is recomputed.
final recipeFullProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/recipes/$id/full');
  return Map<String, dynamic>.from(resp.data as Map);
});

/// Simulated selling price for the cost panel. null -> use the recipe's own
/// selling_price (server fallback). Mirrors the web cost-panel "Prix de vente".
final recipeSellingPriceProvider =
    StateProvider.autoDispose.family<double?, String>((ref, id) => null);

final recipeCostProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>?, String>((ref, id) async {
  final full = await ref.read(recipeFullProvider(id).future);
  final vid = (full['recipe'] as Map?)?['current_version_id'];
  if (vid == null) return null;
  final override = ref.watch(recipeSellingPriceProvider(id));
  try {
    final resp = await ref.read(apiClientProvider).dio.post(
          '/recipes/$id/versions/$vid/compute-cost',
          data: override != null ? {'selling_price': override} : null,
        );
    return Map<String, dynamic>.from(resp.data as Map);
  } catch (_) {
    return null; // viewer role / no prices — just hide the figure
  }
});

final _productsPickerProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref
      .read(apiClientProvider)
      .dio
      .get('/products/enriched', queryParameters: {'limit': 500});
  return (resp.data as List);
});

class RecipeDetailScreen extends ConsumerWidget {
  const RecipeDetailScreen({super.key, required this.recipeId, required this.recipeName});
  final String recipeId;
  final String recipeName;

  Future<void> _reload(WidgetRef ref) async {
    ref.invalidate(recipeFullProvider(recipeId));
    ref.invalidate(recipeCostProvider(recipeId));
    await ref.read(recipeFullProvider(recipeId).future);
  }

  /// Persist the current ingredient list as a new version (which becomes current).
  Future<bool> _saveIngredients(
      WidgetRef ref, ScaffoldMessengerState messenger, List<Map<String, dynamic>> ingredients) async {
    try {
      await ref.read(apiClientProvider).dio.post('/recipes/$recipeId/versions', data: {
        'ingredients': ingredients
            .map((i) => {
                  'product_id': i['product_id'],
                  'qty': i['qty'],
                  'qty_normalized': i['qty'],
                  'loss_pct': i['loss_pct'] ?? 0,
                  'yield_pct': i['yield_pct'] ?? 100,
                })
            .toList(),
      });
      await _reload(ref);
      return true;
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
      return false;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fullAsync = ref.watch(recipeFullProvider(recipeId));
    // id -> nom produit, pour afficher les ingrédients (/full ne renvoie que l'id)
    final productNames = <String, String>{
      for (final p in (ref.watch(_productsPickerProvider).valueOrNull ?? const []))
        '${p['id']}': '${p['name'] ?? ''}',
    };

    return Scaffold(
      appBar: AppBar(
        title: Text(recipeName, style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      floatingActionButton: fullAsync.hasValue
          ? FloatingActionButton.extended(
              onPressed: () => _addIngredient(context, ref, fullAsync.value!),
              icon: const Icon(Icons.add),
              label: const Text('Ingrédient'),
            )
          : null,
      body: RefreshIndicator(
        onRefresh: () => _reload(ref),
        child: fullAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(children: [
                const Icon(Icons.cloud_off, size: 32, color: kMuted),
                const SizedBox(height: 10),
                const Text('Chargement impossible',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 12),
                FilledButton.icon(
                    onPressed: () => _reload(ref),
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('Réessayer')),
              ]),
            ),
          ]),
          data: (full) {
            final recipe = Map<String, dynamic>.from(full['recipe'] as Map? ?? {});
            final ingredients =
                (full['ingredients'] as List? ?? const []).cast<Map<String, dynamic>>();
            final portions = recipe['yield_qty'];

            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
              children: [
                // --- Coût matière, marge, food cost + simulation de prix ---
                _CostCard(
                  recipeId: recipeId,
                  portions: portions,
                  onEditPortions: () => _editPortions(context, ref, portions),
                ),
                const SizedBox(height: 16),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 4),
                  child: Text('Ingrédients',
                      style: TextStyle(fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
                ),
                const SizedBox(height: 8),
                if (ingredients.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 28),
                    child: Center(
                      child: Text('Aucun ingrédient. Touchez « Ingrédient » pour en ajouter.',
                          textAlign: TextAlign.center, style: TextStyle(color: kMuted)),
                    ),
                  )
                else
                  ...ingredients.asMap().entries.map((e) {
                    final ing = e.value;
                    final pid = ing['product_id'];
                    final name = (pid != null ? productNames['$pid'] : null) ??
                        ing['ingredient_name'] ??
                        'Produit';
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        title: Text(name),
                        subtitle: Text(
                            'Qté ${_fmt(ing['qty'])}'
                            '${(ing['loss_pct'] ?? 0) != 0 ? ' · perte ${_fmt(ing['loss_pct'])}%' : ''}'),
                        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                          IconButton(
                            icon: const Icon(Icons.edit, size: 20),
                            tooltip: 'Modifier',
                            onPressed: () =>
                                _editIngredient(context, ref, full, e.key),
                          ),
                          IconButton(
                            icon: const Icon(Icons.delete_outline, size: 20),
                            tooltip: 'Supprimer',
                            onPressed: () => _deleteIngredient(context, ref, full, e.key),
                          ),
                        ]),
                      ),
                    );
                  }),
                _InstructionsSection(
                  instructions: (full['instructions'] as List?) ?? const [],
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  // --- Actions --------------------------------------------------------------

  List<Map<String, dynamic>> _currentList(Map<String, dynamic> full) =>
      (full['ingredients'] as List? ?? const [])
          .cast<Map<String, dynamic>>()
          .map((i) => Map<String, dynamic>.from(i))
          .toList();

  Future<void> _addIngredient(BuildContext context, WidgetRef ref, Map<String, dynamic> full) async {
    final messenger = ScaffoldMessenger.of(context);
    final result = await _showIngredientDialog(context, ref);
    if (result == null) return;
    final list = _currentList(full)..add(result);
    if (await _saveIngredients(ref, messenger, list)) {
      messenger.showSnackBar(const SnackBar(content: Text('Ingrédient ajouté.')));
    }
  }

  Future<void> _editIngredient(
      BuildContext context, WidgetRef ref, Map<String, dynamic> full, int index) async {
    final messenger = ScaffoldMessenger.of(context);
    final list = _currentList(full);
    final result = await _showIngredientDialog(context, ref, initial: list[index]);
    if (result == null) return;
    list[index] = result;
    if (await _saveIngredients(ref, messenger, list)) {
      messenger.showSnackBar(const SnackBar(content: Text('Ingrédient modifié.')));
    }
  }

  Future<void> _deleteIngredient(
      BuildContext context, WidgetRef ref, Map<String, dynamic> full, int index) async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Supprimer cet ingrédient ?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Supprimer')),
        ],
      ),
    );
    if (ok != true) return;
    final list = _currentList(full)..removeAt(index);
    if (await _saveIngredients(ref, messenger, list)) {
      messenger.showSnackBar(const SnackBar(content: Text('Ingrédient supprimé.')));
    }
  }

  Future<void> _editPortions(BuildContext context, WidgetRef ref, dynamic current) async {
    final messenger = ScaffoldMessenger.of(context);
    final ctrl = TextEditingController(text: current == null ? '' : _fmt(current));
    final val = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Nombre de portions'),
        content: TextField(
          controller: ctrl,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Portions'),
          autofocus: true,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('Enregistrer')),
        ],
      ),
    );
    final parsed = double.tryParse((val ?? '').replaceAll(',', '.'));
    if (parsed == null) return;
    try {
      await ref.read(apiClientProvider).dio.put('/recipes/$recipeId', data: {'yield_qty': parsed});
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Portions mises à jour.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  /// Dialog: pick a product + quantity (+ loss/yield). Returns the ingredient map.
  Future<Map<String, dynamic>?> _showIngredientDialog(BuildContext context, WidgetRef ref,
      {Map<String, dynamic>? initial}) async {
    final products = await ref.read(_productsPickerProvider.future);
    if (!context.mounted) return null;
    return showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => _IngredientDialog(products: products, initial: initial),
    );
  }
}

String _fmt(dynamic v) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  if (n == null) return '$v';
  return n == n.roundToDouble() ? '${n.toInt()}' : '$n';
}

class _IngredientDialog extends StatefulWidget {
  const _IngredientDialog({required this.products, this.initial});
  final List<dynamic> products;
  final Map<String, dynamic>? initial;

  @override
  State<_IngredientDialog> createState() => _IngredientDialogState();
}

class _IngredientDialogState extends State<_IngredientDialog> {
  final _formKey = GlobalKey<FormState>();
  String? _productId;
  late final TextEditingController _qty;
  late final TextEditingController _loss;
  late final TextEditingController _yield;

  @override
  void initState() {
    super.initState();
    _productId = widget.initial?['product_id'] as String?;
    _qty = TextEditingController(
        text: widget.initial?['qty'] == null ? '' : _fmt(widget.initial!['qty']));
    _loss = TextEditingController(
        text: (widget.initial?['loss_pct'] ?? 0) == 0 ? '' : _fmt(widget.initial!['loss_pct']));
    _yield = TextEditingController(
        text: (widget.initial?['yield_pct'] ?? 100) == 100 ? '' : _fmt(widget.initial!['yield_pct']));
  }

  @override
  void dispose() {
    _qty.dispose();
    _loss.dispose();
    _yield.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.initial == null ? 'Ajouter un ingrédient' : 'Modifier l\'ingrédient'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                initialValue: _productId,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Produit'),
                items: [
                  for (final p in widget.products)
                    DropdownMenuItem(
                      value: '${p['id']}',
                      child: Text('${p['name'] ?? ''}', overflow: TextOverflow.ellipsis),
                    ),
                ],
                validator: (v) => (v == null || v.isEmpty) ? 'Produit requis' : null,
                onChanged: (v) => setState(() => _productId = v),
              ),
              const SizedBox(height: 6),
              TextFormField(
                controller: _qty,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Quantité (unité de base)'),
                validator: (v) {
                  final n = double.tryParse((v ?? '').replaceAll(',', '.'));
                  return (n == null || n <= 0) ? 'Quantité > 0' : null;
                },
              ),
              const SizedBox(height: 6),
              TextFormField(
                controller: _loss,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Perte % (optionnel)'),
              ),
              const SizedBox(height: 6),
              TextFormField(
                controller: _yield,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                    labelText: 'Rendement % (optionnel, défaut 100)'),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            if (!_formKey.currentState!.validate()) return;
            Navigator.pop(context, {
              'product_id': _productId,
              'qty': double.tryParse(_qty.text.replaceAll(',', '.')),
              'loss_pct': double.tryParse(_loss.text.replaceAll(',', '.')) ?? 0,
              'yield_pct': double.tryParse(_yield.text.replaceAll(',', '.')) ?? 100,
            });
          },
          child: const Text('Enregistrer'),
        ),
      ],
    );
  }
}

/// Cost panel — the mobile equivalent of the web `cost-panel.tsx`: material cost,
/// cost/portion, food cost %, estimated margin, a "missing prices" warning, and a
/// live "simulate a selling price" input that re-runs compute-cost with a body.
class _CostCard extends ConsumerStatefulWidget {
  const _CostCard({
    required this.recipeId,
    required this.portions,
    required this.onEditPortions,
  });
  final String recipeId;
  final dynamic portions;
  final VoidCallback onEditPortions;

  @override
  ConsumerState<_CostCard> createState() => _CostCardState();
}

class _CostCardState extends ConsumerState<_CostCard> {
  final _price = TextEditingController();

  @override
  void dispose() {
    _price.dispose();
    super.dispose();
  }

  Widget _metric(String label, String value, {Color? color}) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: kMuted)),
          const SizedBox(height: 2),
          Text(value,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: color)),
        ],
      );

  @override
  Widget build(BuildContext context) {
    final cost = ref.watch(recipeCostProvider(widget.recipeId)).valueOrNull;
    final cpp = cost?['cost_per_portion'] as num?;
    final fc = cost?['food_cost_pct'] as num?;
    final total = cost?['computed_cost_total'] as num?;
    final margin = cost?['margin_estimated'] as num?;
    final missing = cost?['has_missing_prices'] == true;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                    child: _metric('Portions',
                        widget.portions == null ? '—' : _fmt(widget.portions))),
                Expanded(child: _metric('Coût / portion', cpp == null ? '—' : eur(cpp))),
                OutlinedButton(
                    onPressed: widget.onEditPortions, child: const Text('Portions')),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(child: _metric('Coût matière', total == null ? '—' : eur(total))),
                Expanded(
                    child: _metric('Marge / portion', margin == null ? '—' : eur(margin),
                        color: margin == null ? null : (margin >= 0 ? kGood : kBad))),
                Expanded(
                    child: _metric('Food cost', fc == null ? '—' : '${fc.round()} %',
                        color: fc == null ? null : (fc >= 33 ? kBad : kGood))),
              ],
            ),
            if (missing) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                    color: const Color(0xFFF6EAD4), borderRadius: BorderRadius.circular(8)),
                child: const Row(children: [
                  Icon(Icons.info_outline, size: 16, color: kWarn),
                  SizedBox(width: 6),
                  Expanded(
                      child: Text("Coût partiel : certains ingrédients n'ont pas de prix.",
                          style: TextStyle(fontSize: 12, color: Color(0xFF8A6D3B)))),
                ]),
              ),
            ],
            const Divider(height: 26),
            const Text('Simuler un prix de vente / portion',
                style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _price,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(
                        isDense: true, hintText: 'ex. 12,50', prefixText: '€ '),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () {
                    ref.read(recipeSellingPriceProvider(widget.recipeId).notifier).state =
                        double.tryParse(_price.text.replaceAll(',', '.'));
                  },
                  child: const Text('Calculer'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Recipe procedure — the ordered steps returned by GET /recipes/{id}/full
/// (`instructions`). Hidden when there are none. Mirrors the web recipe page.
class _InstructionsSection extends StatelessWidget {
  const _InstructionsSection({required this.instructions});
  final List instructions;

  @override
  Widget build(BuildContext context) {
    if (instructions.isEmpty) return const SizedBox.shrink();
    final steps = instructions.map((e) => Map<String, dynamic>.from(e as Map)).toList()
      ..sort((a, b) =>
          ((a['step_number'] ?? 0) as num).compareTo((b['step_number'] ?? 0) as num));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 20),
        const Text('Procédure',
            style: TextStyle(
                fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        ...steps.asMap().entries.map((e) {
          final n = e.value['step_number'] ?? (e.key + 1);
          return Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 24,
                  height: 24,
                  alignment: Alignment.center,
                  decoration:
                      const BoxDecoration(color: Color(0xFFEFE1D3), shape: BoxShape.circle),
                  child: Text('$n',
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w700, color: kTerracotta)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('${e.value['content'] ?? ''}',
                      style: const TextStyle(fontSize: 13.5, height: 1.35)),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }
}
