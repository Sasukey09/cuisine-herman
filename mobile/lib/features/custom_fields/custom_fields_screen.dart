import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kSecondary;

final _fieldsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final r = await ref.read(apiClientProvider).dio.get('/custom-fields/');
  return r.data as List<dynamic>;
});

class CustomFieldsScreen extends ConsumerStatefulWidget {
  const CustomFieldsScreen({super.key});

  @override
  ConsumerState<CustomFieldsScreen> createState() => _CustomFieldsScreenState();
}

class _CustomFieldsScreenState extends ConsumerState<CustomFieldsScreen> {
  final _label = TextEditingController();
  final _options = TextEditingController();
  String _target = 'product';
  String _type = 'text';
  bool _required = false;

  // value editor
  String _valTarget = 'product';
  String? _entityId;
  List<dynamic> _entities = [];
  List<dynamic> _defs = [];
  final Map<String, dynamic> _values = {};

  @override
  void dispose() {
    _label.dispose();
    _options.dispose();
    super.dispose();
  }

  void _snack(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _create() async {
    if (_label.text.trim().isEmpty) {
      _snack('Libellé requis.');
      return;
    }
    try {
      await ref.read(apiClientProvider).dio.post('/custom-fields/', data: {
        'label': _label.text.trim(),
        'target': _target,
        'type': _type,
        'required': _required,
        'options': _type == 'select'
            ? _options.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList()
            : [],
      });
      _label.clear();
      _options.clear();
      setState(() => _required = false);
      ref.invalidate(_fieldsProvider);
      _snack('Champ créé.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    }
  }

  Future<void> _loadEntities() async {
    final path = _valTarget == 'product' ? '/products/' : '/recipes/';
    final r = await ref.read(apiClientProvider).dio.get(path, queryParameters: {'limit': 200});
    setState(() {
      _entities = r.data as List;
      _entityId = null;
      _defs = [];
      _values.clear();
    });
  }

  Future<void> _loadValues() async {
    if (_entityId == null) return;
    final r = await ref
        .read(apiClientProvider)
        .dio
        .get('/custom-fields/values/$_valTarget/$_entityId');
    final data = r.data as Map<String, dynamic>;
    setState(() {
      _defs = data['definitions'] as List;
      _values
        ..clear()
        ..addAll((data['values'] as Map).cast<String, dynamic>());
    });
  }

  Future<void> _saveValues() async {
    try {
      await ref
          .read(apiClientProvider)
          .dio
          .put('/custom-fields/values/$_valTarget/$_entityId', data: {'values': _values});
      _snack('Valeurs enregistrées.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final fields = ref.watch(_fieldsProvider);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Nouveau champ', style: TextStyle(fontWeight: FontWeight.bold)),
        TextField(controller: _label, decoration: const InputDecoration(labelText: 'Libellé')),
        Row(
          children: [
            const Text('Cible : '),
            DropdownButton<String>(
              value: _target,
              items: const [
                DropdownMenuItem(value: 'product', child: Text('Produit')),
                DropdownMenuItem(value: 'recipe', child: Text('Recette')),
              ],
              onChanged: (v) => setState(() => _target = v ?? 'product'),
            ),
            const SizedBox(width: 12),
            const Text('Type : '),
            DropdownButton<String>(
              value: _type,
              items: const [
                DropdownMenuItem(value: 'text', child: Text('Texte')),
                DropdownMenuItem(value: 'number', child: Text('Nombre')),
                DropdownMenuItem(value: 'boolean', child: Text('Oui/Non')),
                DropdownMenuItem(value: 'select', child: Text('Liste')),
              ],
              onChanged: (v) => setState(() => _type = v ?? 'text'),
            ),
          ],
        ),
        if (_type == 'select')
          TextField(
            controller: _options,
            decoration: const InputDecoration(labelText: 'Choix (séparés par virgules)'),
          ),
        // Case « obligatoire » — présente au web, absente du mobile jusqu'ici :
        // impossible de définir un champ requis.
        CheckboxListTile(
          value: _required,
          onChanged: (v) => setState(() => _required = v ?? false),
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          dense: true,
          title: const Text('Champ obligatoire'),
        ),
        const SizedBox(height: 8),
        FilledButton.icon(onPressed: _create, icon: const Icon(Icons.add), label: const Text('Créer')),
        const Divider(height: 32),

        const Text('Renseigner une fiche', style: TextStyle(fontWeight: FontWeight.bold)),
        Row(
          children: [
            const Text('Type : '),
            DropdownButton<String>(
              value: _valTarget,
              items: const [
                DropdownMenuItem(value: 'product', child: Text('Produit')),
                DropdownMenuItem(value: 'recipe', child: Text('Recette')),
              ],
              onChanged: (v) {
                setState(() => _valTarget = v ?? 'product');
                _loadEntities();
              },
            ),
            const SizedBox(width: 8),
            FilledButton.tonal(onPressed: _loadEntities, child: const Text('Charger')),
          ],
        ),
        if (_entities.isNotEmpty)
          DropdownButton<String>(
            isExpanded: true,
            value: _entityId,
            hint: const Text('Choisir une fiche'),
            items: _entities
                .map((e) => DropdownMenuItem(
                      value: '${(e as Map)['id']}',
                      child: Text('${e['name']}', overflow: TextOverflow.ellipsis),
                    ))
                .toList(),
            onChanged: (v) {
              setState(() => _entityId = v);
              _loadValues();
            },
          ),
        ..._defs.map((d) {
          final dd = d as Map<String, dynamic>;
          final key = '${dd['key']}';
          final type = '${dd['type']}';
          if (type == 'boolean') {
            return SwitchListTile(
              title: Text('${dd['label']}'),
              value: _values[key] == true,
              onChanged: (v) => setState(() => _values[key] = v),
            );
          }
          if (type == 'select') {
            return Row(
              children: [
                Expanded(child: Text('${dd['label']}')),
                DropdownButton<String>(
                  value: _values[key] as String?,
                  hint: const Text('—'),
                  items: ((dd['options'] as List?) ?? [])
                      .map((o) => DropdownMenuItem(value: '$o', child: Text('$o')))
                      .toList(),
                  onChanged: (v) => setState(() => _values[key] = v),
                ),
              ],
            );
          }
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: TextFormField(
              initialValue: _values[key]?.toString() ?? '',
              keyboardType: type == 'number' ? TextInputType.number : TextInputType.text,
              decoration: InputDecoration(labelText: '${dd['label']}'),
              onChanged: (v) => _values[key] = v,
            ),
          );
        }),
        if (_defs.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: FilledButton.icon(
                onPressed: _saveValues, icon: const Icon(Icons.save), label: const Text('Enregistrer')),
          ),
        const Divider(height: 32),

        const Text('Champs définis',
            style: TextStyle(fontFamily: 'Newsreader', fontSize: 15.5, fontWeight: FontWeight.w600)),
        const SizedBox(height: 10),
        fields.maybeWhen(
          data: (rows) => rows.isEmpty
              ? const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text('Aucun champ.', style: TextStyle(color: kMuted)))
              : Column(
                  children: [
                    for (final f in rows) ...[
                      _fieldCard(f as Map<String, dynamic>),
                      const SizedBox(height: 10),
                    ],
                  ],
                ),
          orElse: () => const Padding(
              padding: EdgeInsets.all(8), child: Center(child: CircularProgressIndicator())),
        ),
      ],
    );
  }

  Widget _fieldCard(Map<String, dynamic> ff) {
    const targets = {'product': 'Produits', 'recipe': 'Recettes'};
    const types = {
      'text': 'Texte',
      'number': 'Nombre',
      'boolean': 'Booléen',
      'select': 'Multi-sél.',
      'date': 'Date',
    };
    final scope = targets['${ff['target']}'] ?? '${ff['target']}';
    final req = ff['required'] == true ? 'Obligatoire' : 'Facultatif';
    final typeLabel = types['${ff['type']}'] ?? '${ff['type']}';
    return MockCard(
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${ff['label']}',
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text('$scope · $req', style: const TextStyle(fontSize: 12, color: kMuted)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
            decoration: BoxDecoration(color: kSecondary, borderRadius: BorderRadius.circular(7)),
            child: Text(typeLabel, style: const TextStyle(fontSize: 11.5, color: Color(0xFF8A7F70))),
          ),
          InkWell(
            onTap: () async {
              try {
                await ref.read(apiClientProvider).dio.delete('/custom-fields/${ff['id']}');
                ref.invalidate(_fieldsProvider);
              } catch (e) {
                _snack(apiErrorMessage(e));
              }
            },
            child: const Padding(
              padding: EdgeInsets.only(left: 8),
              child: Icon(Icons.delete_outline, size: 18, color: kMuted),
            ),
          ),
        ],
      ),
    );
  }
}
