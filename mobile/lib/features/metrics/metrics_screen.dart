import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_error.dart';
import '../../core/providers.dart';

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
  List<dynamic>? _evaluation;
  bool _creating = false;

  @override
  void dispose() {
    _name.dispose();
    _formula.dispose();
    super.dispose();
  }

  void _snack(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

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
      final r = await ref
          .read(apiClientProvider)
          .dio
          .get('/metrics/evaluate/recipe/$_recipeId');
      setState(() => _evaluation = (r.data as Map<String, dynamic>)['metrics'] as List);
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
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Créez vos calculs avec des formules. Ex. : cost_per_portion * 3',
            style: TextStyle(color: Colors.grey)),
        const SizedBox(height: 12),
        TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nom')),
        const SizedBox(height: 8),
        TextField(
          controller: _formula,
          decoration: const InputDecoration(labelText: 'Formule', hintText: 'cost_per_portion * 3'),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            const Text('Format : '),
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
                        _formula.text =
                            _formula.text.isEmpty ? name : '${_formula.text} $name';
                      },
                    ))
                .toList(),
          ),
          orElse: () => const SizedBox.shrink(),
        ),
        const SizedBox(height: 8),
        FilledButton.icon(
          onPressed: _creating ? null : _create,
          icon: const Icon(Icons.add),
          label: const Text('Créer'),
        ),
        const Divider(height: 32),
        const Text('Tester sur une recette', style: TextStyle(fontWeight: FontWeight.bold)),
        recipes.maybeWhen(
          data: (rs) => Row(
            children: [
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
                    setState(() {
                      _recipeId = v;
                      _evaluation = null;
                    });
                    _evaluate();
                  },
                ),
              ),
            ],
          ),
          orElse: () => const SizedBox.shrink(),
        ),
        if (_evaluation != null)
          ..._evaluation!.map((m) {
            final mm = m as Map<String, dynamic>;
            return ListTile(
              dense: true,
              title: Text('${mm['name']}'),
              trailing: Text(mm['error'] != null ? '${mm['error']}' : '${mm['value'] ?? '—'}'),
            );
          }),
        const Divider(height: 32),
        const Text('Mes indicateurs', style: TextStyle(fontWeight: FontWeight.bold)),
        metrics.maybeWhen(
          data: (rows) => rows.isEmpty
              ? const Padding(
                  padding: EdgeInsets.all(8),
                  child: Text('Aucun indicateur.', style: TextStyle(color: Colors.grey)))
              : Column(
                  children: rows.map((m) {
                    final mm = m as Map<String, dynamic>;
                    return ListTile(
                      dense: true,
                      title: Text('${mm['name']}'),
                      subtitle: Text('${mm['formula']}'),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () async {
                          try {
                            await ref.read(apiClientProvider).dio.delete('/metrics/${mm['id']}');
                            ref.invalidate(_metricsProvider);
                          } catch (e) {
                            _snack(apiErrorMessage(e));
                          }
                        },
                      ),
                    );
                  }).toList(),
                ),
          orElse: () => const Padding(
              padding: EdgeInsets.all(8), child: Center(child: CircularProgressIndicator())),
        ),
      ],
    );
  }
}
