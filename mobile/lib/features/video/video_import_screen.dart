import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kBorder;

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
      setState(() =>
          _savedInfo = 'Fiche enregistrée. Coût/portion : ${cost['cost_per_portion'] ?? 0} €');
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
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
      children: [
        // --- Drop-zone card ----------------------------------------------
        MockCard(
          padding: const EdgeInsets.all(18),
          child: Container(
            padding: const EdgeInsets.fromLTRB(16, 22, 16, 16),
            decoration: BoxDecoration(
              color: const Color(0xFFFAF6EE),
              border: Border.all(color: const Color(0xFFD6C9B4), width: 2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                const Text('🎬', style: TextStyle(fontSize: 30)),
                const SizedBox(height: 4),
                const Text('Importez une vidéo',
                    style: TextStyle(fontFamily: 'serif', fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                const Text("Lien YouTube / Instagram / TikTok / Facebook. L'IA extrait les ingrédients.",
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: kMuted)),
                const SizedBox(height: 12),
                TextField(
                  controller: _url,
                  style: const TextStyle(fontSize: 13),
                  decoration: InputDecoration(
                    isDense: true,
                    fillColor: Colors.white,
                    hintText: 'https://…',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(9),
                      borderSide: const BorderSide(color: kBorder),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _extracting ? null : _extract,
                    child: _extracting
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Text('Analyser'),
                  ),
                ),
              ],
            ),
          ),
        ),

        // --- Extracted recipe card ---------------------------------------
        if (_hasDraft) ...[
          const SizedBox(height: 13),
          MockCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Recette extraite',
                    style: TextStyle(fontFamily: 'serif', fontSize: 15.5, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                const Text('Quantités estimées — à valider',
                    style: TextStyle(fontSize: 12, color: kMuted)),
                const SizedBox(height: 12),
                TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nom')),
                const SizedBox(height: 8),
                TextField(
                  controller: _portions,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Portions'),
                ),
                const SizedBox(height: 12),
                const Text('Ingrédients',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                ..._ings.asMap().entries.map((e) {
                  final i = e.key;
                  final ing = e.value;
                  return Container(
                    decoration: const BoxDecoration(
                      border: Border(bottom: BorderSide(color: Color(0xFFECE4D4))),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(right: 4),
                          child: Text('✓', style: TextStyle(color: kGood, fontSize: 13)),
                        ),
                        Expanded(
                          flex: 3,
                          child: TextFormField(
                            initialValue: ing.name,
                            style: const TextStyle(fontSize: 13),
                            decoration: const InputDecoration(
                                isDense: true, border: InputBorder.none, hintText: 'Ingrédient'),
                            onChanged: (v) => ing.name = v,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: TextFormField(
                            initialValue: ing.qty,
                            keyboardType: TextInputType.number,
                            style: const TextStyle(fontSize: 13),
                            decoration: const InputDecoration(
                                isDense: true, border: InputBorder.none, hintText: 'Qté'),
                            onChanged: (v) => ing.qty = v,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: TextFormField(
                            initialValue: ing.unit,
                            style: const TextStyle(fontSize: 13),
                            decoration: const InputDecoration(
                                isDense: true, border: InputBorder.none, hintText: 'unité'),
                            onChanged: (v) => ing.unit = v,
                          ),
                        ),
                        InkWell(
                          onTap: () => setState(() => _ings.removeAt(i)),
                          child: const Padding(
                            padding: EdgeInsets.only(left: 4),
                            child: Icon(Icons.close, size: 16, color: kMuted),
                          ),
                        ),
                      ],
                    ),
                  );
                }),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => setState(() => _ings.add(_Ing('', '', ''))),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Ajouter un ingrédient'),
                  ),
                ),
                const SizedBox(height: 6),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _saving ? null : _save,
                    child: _saving
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Text('Créer la recette'),
                  ),
                ),
                if (_savedInfo != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(_savedInfo!, style: const TextStyle(color: kGood)),
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
