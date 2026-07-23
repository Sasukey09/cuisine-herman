import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kTerracotta;

final _metricsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final r = await ref.read(apiClientProvider).dio.get('/metrics/');
  return r.data as List<dynamic>;
});
final _variablesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final r = await ref.read(apiClientProvider).dio.get('/metrics/variables');
  return r.data as List<dynamic>;
});
final _recipesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final r = await ref.read(apiClientProvider).dio.get('/recipes/', queryParameters: {'limit': 200});
  return r.data as List<dynamic>;
});

class MetricsScreen extends ConsumerStatefulWidget {
  const MetricsScreen({super.key});

  @override
  ConsumerState<MetricsScreen> createState() => _MetricsScreenState();
}

class _MetricsScreenState extends ConsumerState<MetricsScreen> {
  final _name = TextEditingController();
  final _formula = TextEditingController();
  String _format = 'number';
  String? _recipeId;
  Map<String, Map<String, dynamic>> _evalById = {};
  bool _creating = false;

  @override
  void dispose() {
    _name.dispose();
    _formula.dispose();
    super.dispose();
  }

  void _snack(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  String _fmtVal(num? v, String fmt) {
    if (v == null) return '—';
    if (fmt == 'percent') return '${v.toStringAsFixed(1).replaceAll('.', ',')} %';
    if (fmt == 'currency') return eur(v);
    return v.toString().replaceAll('.', ',');
  }

  Future<void> _create() async {
    if (_name.text.trim().isEmpty || _formula.text.trim().isEmpty) {
      _snack('Nom et formule requis.');
      return;
    }
    setState(() => _creating = true);
    try {
      await ref.read(apiClientProvider).dio.post('/metrics/', data: {
        'name': _name.text.trim(),
        'formula': _formula.text.trim(),
        'format': _format,
      });
      _name.clear();
      _formula.clear();
      ref.invalidate(_metricsProvider);
      _snack('Indicateur créé.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  Future<void> _evaluate() async {
    if (_recipeId == null) return;
    try {
      // Passer le prix de vente de la recette : sinon les indicateurs de marge
      // sont faussés (le backend ne le déduit pas ici, contrairement au web).
      final recipes = (ref.read(_recipesProvider).valueOrNull ?? const []).cast<Map>();
      final recipe =
          recipes.firstWhere((r) => '${r['id']}' == _recipeId, orElse: () => const {});
      final sp = recipe['selling_price'];
      final r = await ref.read(apiClientProvider).dio.get(
          '/metrics/evaluate/recipe/$_recipeId',
          queryParameters: sp != null ? {'selling_price': sp} : null);
      final list = (r.data as Map<String, dynamic>)['metrics'] as List;
      setState(() {
        _evalById = {
          for (final e in list.cast<Map>()) '${e['id']}': e.cast<String, dynamic>(),
        };
      });
    } catch (e) {
      _snack(apiErrorMessage(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final metrics = ref.watch(_metricsProvider);
    final variables = ref.watch(_variablesProvider);
    final recipes = ref.watch(_recipesProvider);

    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
      children: [
        // --- Create -------------------------------------------------------
        MockCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Nouvel indicateur',
                  style: TextStyle(fontFamily: 'Newsreader', fontSize: 15.5, fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              const Text('Ex. : cost_per_portion * 3', style: TextStyle(fontSize: 12, color: kMuted)),
              const SizedBox(height: 10),
              TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nom')),
              const SizedBox(height: 8),
              TextField(
                controller: _formula,
                decoration: const InputDecoration(labelText: 'Formule', hintText: 'cost_per_portion * 3'),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  const Text('Format : ', style: TextStyle(color: kMuted)),
                  DropdownButton<String>(
                    value: _format,
                    items: const [
                      DropdownMenuItem(value: 'number', child: Text('Nombre')),
                      DropdownMenuItem(value: 'currency', child: Text('Montant')),
                      DropdownMenuItem(value: 'percent', child: Text('Pourcentage')),
                    ],
                    onChanged: (v) => setState(() => _format = v ?? 'number'),
                  ),
                ],
              ),
              variables.maybeWhen(
                data: (vars) => Wrap(
                  spacing: 6,
                  children: vars
                      .map((v) => ActionChip(
                            label: Text('${(v as Map)['name']}', style: const TextStyle(fontSize: 11)),
                            onPressed: () {
                              final name = '${v['name']}';
                              _formula.text = _formula.text.isEmpty ? name : '${_formula.text} $name';
                            },
                          ))
                      .toList(),
                ),
                orElse: () => const SizedBox.shrink(),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _creating ? null : _create,
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Créer'),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 13),

        // --- Evaluate against a recipe -----------------------------------
        recipes.maybeWhen(
          data: (rs) => MockCard(
            child: Row(
              children: [
                const Text('Tester sur : ', style: TextStyle(color: kMuted, fontSize: 13)),
                Expanded(
                  child: DropdownButton<String>(
                    isExpanded: true,
                    value: _recipeId,
                    hint: const Text('Choisir une recette'),
                    items: rs
                        .map((r) => DropdownMenuItem(
                              value: '${(r as Map)['id']}',
                              child: Text('${r['name']}', overflow: TextOverflow.ellipsis),
                            ))
                        .toList(),
                    onChanged: (v) {
                      setState(() => _recipeId = v);
                      _evaluate();
                    },
                  ),
                ),
              ],
            ),
          ),
          orElse: () => const SizedBox.shrink(),
        ),
        const SizedBox(height: 13),

        // --- The metrics, mockup cards -----------------------------------
        metrics.when(
          loading: () => const Padding(
              padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator())),
          error: (e, _) => Padding(
              padding: const EdgeInsets.all(12), child: Text(apiErrorMessage(e))),
          data: (rows) {
            if (rows.isEmpty) {
              return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: Text('Aucun indicateur.', style: TextStyle(color: kMuted)));
            }
            return Column(
              children: [
                for (final m in rows) ...[
                  _metricCard(context, m as Map<String, dynamic>),
                  const SizedBox(height: 11),
                ],
              ],
            );
          },
        ),
      ],
    );
  }

  Widget _metricCard(BuildContext context, Map<String, dynamic> mm) {
    final id = '${mm['id']}';
    final fmt = '${mm['format'] ?? 'number'}';
    final ev = _evalById[id];
    final hasVal = ev != null && ev['error'] == null && ev['value'] != null;
    final desc = mm['description'];
    return MockCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text('${mm['name']}',
                    style: const TextStyle(fontFamily: 'Newsreader', fontSize: 15, fontWeight: FontWeight.w600)),
              ),
              if (hasVal)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Text(_fmtVal(ev['value'] as num?, fmt),
                      style: const TextStyle(
                          fontFamily: 'Newsreader', fontSize: 20, fontWeight: FontWeight.w600, color: kTerracotta)),
                ),
              InkWell(
                onTap: () async {
                  try {
                    await ref.read(apiClientProvider).dio.delete('/metrics/$id');
                    ref.invalidate(_metricsProvider);
                  } catch (e) {
                    _snack(apiErrorMessage(e));
                  }
                },
                child: const Padding(
                  padding: EdgeInsets.only(left: 6, top: 2),
                  child: Icon(Icons.delete_outline, size: 18, color: kMuted),
                ),
              ),
            ],
          ),
          if (desc != null && '$desc'.isNotEmpty) ...[
            const SizedBox(height: 5),
            Text('$desc', style: const TextStyle(fontSize: 12, color: kMuted)),
          ],
          const SizedBox(height: 9),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              border: Border.all(color: Theme.of(context).dividerColor),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text('${mm['formula']}',
                style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 11.5,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: .8))),
          ),
        ],
      ),
    );
  }
}
