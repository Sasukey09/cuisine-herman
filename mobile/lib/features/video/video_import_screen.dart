import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_error.dart';
import '../../core/providers.dart';

class _Ing {
  _Ing(this.name, this.qty, this.unit);
  String name;
  String qty;
  String unit;
}

class VideoImportScreen extends ConsumerStatefulWidget {
  const VideoImportScreen({super.key});

  @override
  ConsumerState<VideoImportScreen> createState() => _VideoImportScreenState();
}

class _VideoImportScreenState extends ConsumerState<VideoImportScreen> {
  final _url = TextEditingController();
  final _name = TextEditingController();
  final _portions = TextEditingController();
  final List<_Ing> _ings = [];
  bool _extracting = false;
  bool _saving = false;
  bool _hasDraft = false;
  String? _savedInfo;

  @override
  void dispose() {
    _url.dispose();
    _name.dispose();
    _portions.dispose();
    super.dispose();
  }

  Future<void> _extract() async {
    final url = _url.text.trim();
    if (url.isEmpty || _extracting) return;
    setState(() {
      _extracting = true;
      _savedInfo = null;
    });
    try {
      final resp = await ref.read(apiClientProvider).dio.post('/video/extract', data: {'url': url});
      final draft = (resp.data as Map<String, dynamic>)['draft'] as Map<String, dynamic>;
      _name.text = (draft['name'] as String?) ?? '';
      _portions.text = draft['yield_qty'] != null ? '${draft['yield_qty']}' : '';
      _ings
        ..clear()
        ..addAll(((draft['ingredients'] as List?) ?? []).map((e) {
          final m = e as Map<String, dynamic>;
          return _Ing('${m['name'] ?? ''}', m['qty'] != null ? '${m['qty']}' : '', '${m['unit'] ?? ''}');
        }));
      setState(() => _hasDraft = true);
      _snack('Recette extraite — vérifiez les quantités estimées.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _extracting = false);
    }
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) {
      _snack('Donnez un nom à la recette.');
      return;
    }
    setState(() => _saving = true);
    try {
      final ingredients = _ings
          .where((i) => i.name.trim().isNotEmpty)
          .map((i) => {
                'name': i.name.trim(),
                'qty': i.qty.trim().isEmpty ? null : double.tryParse(i.qty.trim()),
                'unit': i.unit.trim().isEmpty ? null : i.unit.trim(),
              })
          .toList();
      final resp = await ref.read(apiClientProvider).dio.post('/video/save', data: {
        'name': _name.text.trim(),
        'yield_qty': _portions.text.trim().isEmpty ? null : double.tryParse(_portions.text.trim()),
        'ingredients': ingredients,
      });
      final cost = (resp.data as Map<String, dynamic>)['cost'] as Map<String, dynamic>;
      setState(() => _savedInfo =
          'Fiche enregistrée. Coût/portion : ${cost['cost_per_portion'] ?? 0} €');
      _snack('Fiche enregistrée et chiffrée.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _snack(String m) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Collez un lien YouTube / TikTok / Instagram. L\'IA en extrait une fiche.',
            style: TextStyle(color: Colors.grey)),
        const SizedBox(height: 12),
        TextField(
          controller: _url,
          decoration: const InputDecoration(labelText: 'Lien vidéo', border: OutlineInputBorder()),
        ),
        const SizedBox(height: 8),
        FilledButton.icon(
          onPressed: _extracting ? null : _extract,
          icon: _extracting
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.auto_awesome),
          label: const Text('Analyser'),
        ),
        if (_hasDraft) ...[
          const Divider(height: 32),
          const Text('Fiche extraite (quantités estimées à valider)',
              style: TextStyle(fontWeight: FontWeight.bold, color: Colors.orange)),
          const SizedBox(height: 8),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nom')),
          const SizedBox(height: 8),
          TextField(
            controller: _portions,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Portions'),
          ),
          const SizedBox(height: 12),
          const Text('Ingrédients'),
          ..._ings.asMap().entries.map((e) {
            final i = e.key;
            final ing = e.value;
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Expanded(
                    flex: 3,
                    child: TextFormField(
                      initialValue: ing.name,
                      decoration: const InputDecoration(isDense: true, hintText: 'Ingrédient'),
                      onChanged: (v) => ing.name = v,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: TextFormField(
                      initialValue: ing.qty,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(isDense: true, hintText: 'Qté'),
                      onChanged: (v) => ing.qty = v,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: TextFormField(
                      initialValue: ing.unit,
                      decoration: const InputDecoration(isDense: true, hintText: 'unité'),
                      onChanged: (v) => ing.unit = v,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, size: 18),
                    onPressed: () => setState(() => _ings.removeAt(i)),
                  ),
                ],
              ),
            );
          }),
          TextButton.icon(
            onPressed: () => setState(() => _ings.add(_Ing('', '', ''))),
            icon: const Icon(Icons.add),
            label: const Text('Ajouter un ingrédient'),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.save),
            label: const Text('Enregistrer la fiche'),
          ),
          if (_savedInfo != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_savedInfo!, style: const TextStyle(color: Colors.green)),
            ),
        ],
      ],
    );
  }
}
