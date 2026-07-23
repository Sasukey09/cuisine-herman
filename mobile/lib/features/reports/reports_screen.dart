import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kSecondary, kInk;

final _sourcesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final r = await ref.read(apiClientProvider).dio.get('/reports/sources');
  return r.data as List<dynamic>;
});

final _savedReportsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final r = await ref.read(apiClientProvider).dio.get('/reports/');
  return r.data as List<dynamic>;
});

class _Filter {
  String field = '';
  String op = 'contains';
  String value = '';
}

const _ops = ['eq', 'ne', 'contains', 'gt', 'gte', 'lt', 'lte'];

const _heading = TextStyle(
    fontFamily: 'Newsreader', fontSize: 15.5, fontWeight: FontWeight.w600);

String _cellText(Object? v) {
  if (v == null) return '';
  if (v is bool) return v ? 'Oui' : 'Non';
  return '$v';
}

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
  String _sortField = '';
  String _sortDir = 'asc';
  final _limitCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  Map<String, dynamic>? _result;
  bool _running = false;
  bool _saving = false;

  @override
  void dispose() {
    _limitCtrl.dispose();
    _nameCtrl.dispose();
    super.dispose();
  }

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
      _sortField = '';
      _result = null;
    });
  }

  Map<String, dynamic> _definition() => {
        'source': _source,
        'columns': _selected.toList(),
        'filters': _filters
            .where((f) => f.field.isNotEmpty)
            .map((f) => {'field': f.field, 'op': f.op, 'value': f.value})
            .toList(),
        'sort': _sortField.isEmpty ? null : {'field': _sortField, 'dir': _sortDir},
        'limit': int.tryParse(_limitCtrl.text.trim()),
      };

  Future<void> _run() async {
    if (_source == null || _selected.isEmpty) {
      _snack('Choisissez une source et des colonnes.');
      return;
    }
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _running = true);
    try {
      final r = await ref
          .read(apiClientProvider)
          .dio
          .post('/reports/run', data: _definition());
      if (!mounted) return;
      setState(() => _result = r.data as Map<String, dynamic>);
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      _snack('Donnez un nom au rapport.');
      return;
    }
    if (_source == null || _selected.isEmpty) {
      _snack('Choisissez une source et des colonnes.');
      return;
    }
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _saving = true);
    try {
      await ref.read(apiClientProvider).dio.post('/reports/', data: {
        'name': name,
        'definition': _definition(),
      });
      if (!mounted) return;
      _nameCtrl.clear();
      ref.invalidate(_savedReportsProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Rapport enregistré.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _runSaved(String id, String name) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _running = true);
    try {
      final r = await ref.read(apiClientProvider).dio.get('/reports/$id/run');
      if (!mounted) return;
      setState(() {
        _result = r.data as Map<String, dynamic>;
        _nameCtrl.text = name;
      });
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Future<void> _deleteSaved(String id) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(apiClientProvider).dio.delete('/reports/$id');
      if (!mounted) return;
      ref.invalidate(_savedReportsProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Rapport supprimé.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  void _exportCsv() {
    final res = _result;
    if (res == null) return;
    final messenger = ScaffoldMessenger.of(context);
    final cols = (res['columns'] as List).cast<dynamic>();
    final rows = (res['rows'] as List);
    final re = RegExp(r'[";\n]');
    String esc(Object? v) {
      final s = _cellText(v).replaceAll('"', '""');
      return re.hasMatch(s) ? '"$s"' : s;
    }

    final buf = <String>[];
    buf.add(cols.map((c) => esc((c as Map)['label'])).join(';'));
    for (final row in rows) {
      final r = row as Map<String, dynamic>;
      buf.add(cols.map((c) => esc(r['${(c as Map)['key']}'])).join(';'));
    }
    final csv = '\uFEFF${buf.join('\n')}';
    Clipboard.setData(ClipboardData(text: csv));
    messenger.showSnackBar(
        SnackBar(content: Text('CSV copié (${rows.length} lignes)')));
  }

  @override
  Widget build(BuildContext context) {
    final sources = ref.watch(_sourcesProvider);
    final saved = ref.watch(_savedReportsProvider);
    return sources.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text(apiErrorMessage(e))),
      data: (list) {
        _initSource(list);
        return ListView(
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
          children: [
            const Text('Modèles', style: _heading),
            const SizedBox(height: 10),
            for (final s in list) ...[
              _sourceCard(s as Map<String, dynamic>, list),
              const SizedBox(height: 11),
            ],
            const SizedBox(height: 4),
            const Text('Rapport personnalisé', style: _heading),
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
            const SizedBox(height: 6),
            Row(
              children: [
                const Text('Trier : '),
                Expanded(
                  child: DropdownButton<String>(
                    isExpanded: true,
                    value: _sortField,
                    items: [
                      const DropdownMenuItem(value: '', child: Text('—')),
                      ..._columns.map((c) => DropdownMenuItem(
                            value: '${(c as Map)['key']}',
                            child: Text('${c['label']}', overflow: TextOverflow.ellipsis),
                          )),
                    ],
                    onChanged: (v) => setState(() => _sortField = v ?? ''),
                  ),
                ),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _sortDir,
                  items: const [
                    DropdownMenuItem(value: 'asc', child: Text('croissant')),
                    DropdownMenuItem(value: 'desc', child: Text('décroissant')),
                  ],
                  onChanged: (v) => setState(() => _sortDir = v ?? 'asc'),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                const Text('Limite : '),
                SizedBox(
                  width: 90,
                  child: TextField(
                    controller: _limitCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(isDense: true, hintText: 'ex. 100'),
                  ),
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
            Wrap(
              spacing: 10,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                FilledButton.icon(
                  onPressed: _running ? null : _run,
                  icon: _running
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.play_arrow),
                  label: const Text('Exécuter'),
                ),
                SizedBox(
                  width: 170,
                  child: TextField(
                    controller: _nameCtrl,
                    decoration: const InputDecoration(isDense: true, hintText: 'Nom du rapport'),
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: _saving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.save_outlined),
                  label: const Text('Enregistrer'),
                ),
              ],
            ),
            if (_result != null) ...[
              const Divider(height: 32),
              Row(
                children: [
                  Text('${_result!['count']} ligne(s)',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                  const Spacer(),
                  TextButton.icon(
                    onPressed:
                        (_result!['rows'] as List).isEmpty ? null : _exportCsv,
                    icon: const Icon(Icons.copy_all_outlined, size: 18),
                    label: const Text('Export CSV'),
                  ),
                ],
              ),
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
                        return DataCell(Text(_cellText(r[key])));
                      }).toList(),
                    );
                  }).toList(),
                ),
              ),
            ],
            const Divider(height: 32),
            const Text('Rapports enregistrés', style: _heading),
            const SizedBox(height: 10),
            saved.when(
              loading: () => const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: LinearProgressIndicator(),
              ),
              error: (e, _) => Row(
                children: [
                  Expanded(child: Text(apiErrorMessage(e), style: const TextStyle(color: kMuted))),
                  TextButton(
                    onPressed: () => ref.invalidate(_savedReportsProvider),
                    child: const Text('Réessayer'),
                  ),
                ],
              ),
              data: (items) => items.isEmpty
                  ? const Text('Aucun rapport enregistré.',
                      style: TextStyle(color: kMuted))
                  : Column(
                      children: [
                        for (final r in items) ...[
                          _savedCard(r as Map<String, dynamic>),
                          const SizedBox(height: 8),
                        ],
                      ],
                    ),
            ),
          ],
        );
      },
    );
  }

  Widget _savedCard(Map<String, dynamic> r) {
    final id = '${r['id']}';
    final name = '${r['name']}';
    final def = (r['definition'] as Map?) ?? const {};
    final src = '${def['source'] ?? ''}';
    return MockCard(
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: kSecondary,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(src, style: const TextStyle(fontSize: 11.5, color: kInk)),
                ),
              ],
            ),
          ),
          TextButton.icon(
            onPressed: _running ? null : () => _runSaved(id, name),
            icon: const Icon(Icons.play_arrow, size: 18),
            label: const Text('Exécuter'),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline, size: 20),
            tooltip: 'Supprimer',
            onPressed: () => _deleteSaved(id),
          ),
        ],
      ),
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
