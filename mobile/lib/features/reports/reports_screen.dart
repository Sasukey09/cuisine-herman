import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted;

final _sourcesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final r = await ref.read(apiClientProvider).dio.get('/reports/sources');
  return r.data as List<dynamic>;
});

class _Filter {
  String field = '';
  String op = 'contains';
  String value = '';
}

const _ops = ['eq', 'ne', 'contains', 'gt', 'gte', 'lt', 'lte'];

class ReportsScreen extends ConsumerStatefulWidget {
  const ReportsScreen({super.key});

  @override
  ConsumerState<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends ConsumerState<ReportsScreen> {
  String? _source;
  List<dynamic> _columns = []; // available columns for source
  final Set<String> _selected = {};
  final List<_Filter> _filters = [];
  Map<String, dynamic>? _result;
  bool _running = false;

  void _snack(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  void _initSource(List<dynamic> sources) {
    if (_source == null && sources.isNotEmpty) {
      final first = sources.first as Map<String, dynamic>;
      _source = '${first['key']}';
      _columns = first['columns'] as List;
      _selected
        ..clear()
        ..addAll(_columns.map((c) => '${(c as Map)['key']}'));
    }
  }

  void _changeSource(List<dynamic> sources, String key) {
    final s = sources.firstWhere((e) => '${(e as Map)['key']}' == key) as Map<String, dynamic>;
    setState(() {
      _source = key;
      _columns = s['columns'] as List;
      _selected
        ..clear()
        ..addAll(_columns.map((c) => '${(c as Map)['key']}'));
      _filters.clear();
      _result = null;
    });
  }

  Future<void> _run() async {
    if (_source == null || _selected.isEmpty) {
      _snack('Choisissez une source et des colonnes.');
      return;
    }
    setState(() => _running = true);
    try {
      final r = await ref.read(apiClientProvider).dio.post('/reports/run', data: {
        'source': _source,
        'columns': _selected.toList(),
        'filters': _filters
            .where((f) => f.field.isNotEmpty)
            .map((f) => {'field': f.field, 'op': f.op, 'value': f.value})
            .toList(),
      });
      setState(() => _result = r.data as Map<String, dynamic>);
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sources = ref.watch(_sourcesProvider);
    return sources.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text(apiErrorMessage(e))),
      data: (list) {
        _initSource(list);
        return ListView(
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
          children: [
            const Text('Modèles',
                style: TextStyle(fontFamily: 'Newsreader', fontSize: 15.5, fontWeight: FontWeight.w600)),
            const SizedBox(height: 10),
            for (final s in list) ...[
              _sourceCard(s as Map<String, dynamic>, list),
              const SizedBox(height: 11),
            ],
            const SizedBox(height: 4),
            const Text('Rapport personnalisé',
                style: TextStyle(fontFamily: 'Newsreader', fontSize: 15.5, fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Row(
              children: [
                const Text('Source : '),
                DropdownButton<String>(
                  value: _source,
                  items: list
                      .map((s) => DropdownMenuItem(
                            value: '${(s as Map)['key']}',
                            child: Text('${s['label']}'),
                          ))
                      .toList(),
                  onChanged: (v) => v != null ? _changeSource(list, v) : null,
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text('Colonnes', style: TextStyle(fontWeight: FontWeight.bold)),
            Wrap(
              spacing: 8,
              children: _columns.map((c) {
                final cc = c as Map<String, dynamic>;
                final key = '${cc['key']}';
                return FilterChip(
                  label: Text('${cc['label']}'),
                  selected: _selected.contains(key),
                  onSelected: (sel) => setState(
                      () => sel ? _selected.add(key) : _selected.remove(key)),
                );
              }).toList(),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Text('Filtres', style: TextStyle(fontWeight: FontWeight.bold)),
                const Spacer(),
                TextButton.icon(
                  onPressed: () => setState(() => _filters.add(_Filter())),
                  icon: const Icon(Icons.add),
                  label: const Text('Ajouter'),
                ),
              ],
            ),
            ..._filters.asMap().entries.map((e) {
              final f = e.value;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Expanded(
                      child: DropdownButton<String>(
                        isExpanded: true,
                        value: f.field.isEmpty ? null : f.field,
                        hint: const Text('colonne'),
                        items: _columns
                            .map((c) => DropdownMenuItem(
                                  value: '${(c as Map)['key']}',
                                  child: Text('${c['label']}', overflow: TextOverflow.ellipsis),
                                ))
                            .toList(),
                        onChanged: (v) => setState(() => f.field = v ?? ''),
                      ),
                    ),
                    DropdownButton<String>(
                      value: f.op,
                      items: _ops
                          .map((o) => DropdownMenuItem(value: o, child: Text(o)))
                          .toList(),
                      onChanged: (v) => setState(() => f.op = v ?? 'contains'),
                    ),
                    SizedBox(
                      width: 90,
                      child: TextFormField(
                        initialValue: f.value,
                        decoration: const InputDecoration(isDense: true, hintText: 'valeur'),
                        onChanged: (v) => f.value = v,
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 18),
                      onPressed: () => setState(() => _filters.removeAt(e.key)),
                    ),
                  ],
                ),
              );
            }),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: _running ? null : _run,
              icon: _running
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.play_arrow),
              label: const Text('Exécuter'),
            ),
            if (_result != null) ...[
              const Divider(height: 32),
              Text('${_result!['count']} ligne(s)', style: const TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  columns: (_result!['columns'] as List)
                      .map((c) => DataColumn(label: Text('${(c as Map)['label']}')))
                      .toList(),
                  rows: (_result!['rows'] as List).map((row) {
                    final r = row as Map<String, dynamic>;
                    return DataRow(
                      cells: (_result!['columns'] as List).map((c) {
                        final key = '${(c as Map)['key']}';
                        final v = r[key];
                        return DataCell(Text(v == null ? '' : '$v'));
                      }).toList(),
                    );
                  }).toList(),
                ),
              ),
            ],
          ],
        );
      },
    );
  }

  Widget _sourceCard(Map<String, dynamic> s, List<dynamic> list) {
    const emojis = ['📊', '🍽️', '🚚', '📦', '📈', '🧾'];
    final key = '${s['key']}';
    final idx = list.indexOf(s);
    final emoji = emojis[(idx < 0 ? 0 : idx) % emojis.length];
    final cols = (s['columns'] as List?)?.length ?? 0;
    return MockCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(emoji, style: const TextStyle(fontSize: 24)),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${s['label']}',
                        style: const TextStyle(
                            fontFamily: 'Newsreader', fontSize: 15.5, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 2),
                    Text('$cols colonnes', style: const TextStyle(fontSize: 12, color: kMuted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () {
                _changeSource(list, key);
                _run();
              },
              child: const Text('Générer'),
            ),
          ),
        ],
      ),
    );
  }
}
