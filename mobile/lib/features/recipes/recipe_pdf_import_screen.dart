import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kWarn, kGood;
import '../imports/import_line_editor.dart' show importProductsProvider, importNumField, importPill;
import '../invoices/invoices_screen.dart' show invoiceFileTypes;
import 'recipe_detail_screen.dart';

/// Import de recette PDF sur mobile — pendant de `/import-recette` sur le web.
///
/// C'était le seul module présent sur une seule des deux surfaces (relevé à
/// l'audit global). Le pipeline est entièrement côté serveur — OCR, extraction
/// IA, association produits, chiffrage — donc rien n'est réimplémenté ici :
/// l'écran envoie le fichier, montre la fiche extraite, la laisse corriger, et
/// la valide.
///
/// Réutilise `invoiceFileTypes` (mêmes formats, dont les UTI iOS sans lesquels
/// le sélecteur lève sur iPhone) et `importProductsProvider` (catalogue produits
/// du sélecteur d'association).
///
/// À la différence de l'import facture/devis, une ligne de recette n'a pas
/// d'action « créer / associer / ignorer » : un ingrédient sans produit associé
/// est accepté tel quel, le serveur le signalera comme produit à créer. C'est
/// pourquoi `ImportLineCard` n'est pas réutilisé ici — il pose une question qui
/// ne se pose pas.
class RecipePdfImportScreen extends ConsumerStatefulWidget {
  const RecipePdfImportScreen({super.key});
  @override
  ConsumerState<RecipePdfImportScreen> createState() => _State();
}

/// Une ligne d'ingredient en cours de correction.
///
/// Publique parce que c'est ici que vit la seule logique non triviale de
/// l'ecran : ce qui part au serveur. Une unite vide envoyee comme chaine
/// plutot que null ferait chercher une unite nommee "", et un product_id vide
/// serait rejete par le controle d'appartenance au tenant.
class RecipeIngredientDraft {
  RecipeIngredientDraft({this.name = '', this.qty, this.unit, this.productId, this.matchedName});
  String name;
  num? qty;
  String? unit;
  String? productId;
  String? matchedName;

  factory RecipeIngredientDraft.fromPreview(Map<String, dynamic> m) => RecipeIngredientDraft(
        name: '${m['name'] ?? ''}',
        qty: m['quantity'] as num?,
        unit: m['unit'] as String?,
        productId: m['matched_product_id'] as String?,
        matchedName: m['matched_product_name'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'name': name.trim(),
        'quantity': qty,
        'unit': (unit ?? '').trim().isEmpty ? null : unit!.trim(),
        'product_id': (productId ?? '').isEmpty ? null : productId,
      };
}

class _State extends ConsumerState<RecipePdfImportScreen> {
  final _name = TextEditingController();
  final _servings = TextEditingController();
  final _steps = TextEditingController();

  List<RecipeIngredientDraft>? _ingredients;
  String? _jobId;
  List<String> _unknownUnits = const [];
  String? _note;
  bool _loading = false;
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _servings.dispose();
    _steps.dispose();
    super.dispose();
  }

  Future<void> _pickAndExtract() async {
    final messenger = ScaffoldMessenger.of(context);
    final XFile? file;
    try {
      file = await openFile(acceptedTypeGroups: const [invoiceFileTypes]);
    } catch (_) {
      messenger.showSnackBar(const SnackBar(content: Text("Impossible d'ouvrir le sélecteur.")));
      return;
    }
    if (file == null) return;

    setState(() => _loading = true);
    try {
      final bytes = await file.readAsBytes();
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: file.name),
      });
      final resp = await ref.read(apiClientProvider).dio.post(
            '/recipes/import-pdf',
            data: form,
            options: Options(
              // OCR + extraction IA : des dizaines de secondes. Le délai par
              // défaut couperait la requête en plein travail du serveur.
              sendTimeout: const Duration(seconds: 180),
              receiveTimeout: const Duration(seconds: 180),
            ),
          );
      final data = Map<String, dynamic>.from(resp.data as Map);
      final preview = data['preview'] as Map?;
      if (data['status'] == 'error' || preview == null) {
        messenger.showSnackBar(SnackBar(
          content: Text('${data['error'] ?? 'Aucune recette détectée dans ce document.'}'),
        ));
        return;
      }
      final p = Map<String, dynamic>.from(preview);
      _jobId = data['job_id'] as String?;
      _name.text = '${p['recipe_name'] ?? ''}';
      _servings.text = plainNumber(p['servings'] as num?);
      _steps.text = ((p['instructions'] as List?) ?? const []).join('\n');
      setState(() {
        _ingredients = ((p['ingredients'] as List?) ?? const [])
            .map((e) => RecipeIngredientDraft.fromPreview(Map<String, dynamic>.from(e as Map)))
            .toList();
        _unknownUnits =
            ((p['unknown_units'] as List?) ?? const []).map((e) => '$e').toList();
        _note = p['note'] as String?;
      });
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final name = _name.text.trim();
    if (name.isEmpty) {
      messenger.showSnackBar(const SnackBar(content: Text('Donnez un nom à la recette.')));
      return;
    }
    final kept = _ingredients!.where((i) => i.name.trim().isNotEmpty).toList();
    if (kept.isEmpty) {
      messenger.showSnackBar(const SnackBar(content: Text('Ajoutez au moins un ingrédient.')));
      return;
    }

    setState(() => _saving = true);
    try {
      final resp = await ref.read(apiClientProvider).dio.post(
            '/recipes/import-save',
            queryParameters: _jobId == null ? null : {'job_id': _jobId},
            data: {
              'recipe_name': name,
              'servings': _servings.text.trim().isEmpty
                  ? null
                  : num.tryParse(_servings.text.replaceAll(',', '.')),
              'instructions': _steps.text
                  .split('\n')
                  .map((s) => s.trim())
                  .where((s) => s.isNotEmpty)
                  .toList(),
              'ingredients': kept.map((i) => i.toJson()).toList(),
            },
          );
      final data = Map<String, dynamic>.from(resp.data as Map);
      if (!mounted) return;
      await _showSaved(data);
      navigator.pushReplacement(MaterialPageRoute(
        builder: (_) => RecipeDetailScreen(
          recipeId: '${data['recipe_id']}',
          recipeName: '${data['name'] ?? name}',
        ),
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// Le chiffrage n'existe qu'après enregistrement : c'est le premier moment où
  /// le serveur a vraiment calculé le coût. Le montrer avant d'ouvrir la fiche
  /// évite de le faire chercher.
  Future<void> _showSaved(Map<String, dynamic> data) async {
    final cost = Map<String, dynamic>.from((data['cost'] as Map?) ?? const {});
    final unmatched = ((data['unmatched_ingredients'] as List?) ?? const [])
        .map((e) => '$e')
        .toList();
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(children: [
          const Icon(Icons.check_circle_outline, color: kGood, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text('${data['name'] ?? 'Fiche'} enregistrée')),
        ]),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          _costLine('Coût matière', eur(cost['computed_cost_total'] as num?)),
          _costLine('Coût / portion', eur(cost['cost_per_portion'] as num?)),
          if (cost['food_cost_pct'] != null)
            _costLine('Food cost', '${(cost['food_cost_pct'] as num).toStringAsFixed(1).replaceAll('.', ',')} %'),
          if (cost['margin_estimated'] != null)
            _costLine('Marge estimée', eur(cost['margin_estimated'] as num?)),
          if (cost['has_missing_prices'] == true)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text(
                "Certains ingrédients n'ont pas de prix : le coût est incomplet.",
                style: TextStyle(fontSize: 12.5, color: kWarn),
              ),
            ),
          if (unmatched.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                'Produits à créer : ${unmatched.join(', ')}',
                style: const TextStyle(fontSize: 12.5, color: kMuted),
              ),
            ),
        ]),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Ouvrir la fiche'),
          ),
        ],
      ),
    );
  }

  Widget _costLine(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 3),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(label, style: const TextStyle(fontSize: 13, color: kMuted)),
          const SizedBox(width: 16),
          Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    final ingredients = _ingredients;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Importer une recette', style: TextStyle(fontFamily: 'Newsreader')),
      ),
      body: ingredients == null ? _pickView() : _reviewView(ingredients),
    );
  }

  Widget _pickView() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        const Text('📄', style: TextStyle(fontSize: 34)),
        const SizedBox(height: 8),
        const Text(
          'Importez une fiche recette',
          textAlign: TextAlign.center,
          style: TextStyle(fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 6),
        const Text(
          "PDF texte, PDF scanné ou photo — l'OCR le lit, l'IA en tire une fiche "
          'technique modifiable, associe vos produits et la chiffre.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 13, color: kMuted),
        ),
        const SizedBox(height: 20),
        SizedBox(
          width: double.infinity,
          child: GradientButton(
            label: 'Choisir un PDF ou une photo',
            onPressed: _loading ? null : _pickAndExtract,
            expand: true,
            loading: _loading,
          ),
        ),
        if (_loading)
          const Padding(
            padding: EdgeInsets.only(top: 12),
            child: Text(
              'Lecture et extraction en cours — cela peut prendre une minute.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: kMuted),
            ),
          ),
      ]),
    );
  }

  Widget _reviewView(List<RecipeIngredientDraft> ingredients) {
    // Compté sur les lignes courantes, pas sur l'aperçu : le chiffre doit suivre
    // les corrections de l'utilisateur, sinon il ment dès la première.
    final toLink = ingredients
        .where((i) => i.name.trim().isNotEmpty && (i.productId ?? '').isEmpty)
        .length;
    final total = ingredients.where((i) => i.name.trim().isNotEmpty).length;

    return Column(children: [
      Expanded(
        child: ListView(padding: const EdgeInsets.all(14), children: [
          MockCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Fiche extraite', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 3),
              const Text(
                'Vérifiez les quantités, les unités et les produits avant d\'enregistrer.',
                style: TextStyle(fontSize: 12, color: kMuted),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'Nom de la recette'),
              ),
              TextField(
                controller: _servings,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Portions'),
              ),
              if (_note != null && _note!.trim().isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_note!, style: const TextStyle(fontSize: 12, color: kMuted)),
                ),
              if (_unknownUnits.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    'Unités non reconnues : ${_unknownUnits.join(', ')}. '
                    'Corrigez-les pour que ces lignes entrent dans le coût.',
                    style: const TextStyle(fontSize: 12, color: kWarn),
                  ),
                ),
            ]),
          ),
          const SizedBox(height: 8),
          Row(children: [
            importPill('$total ingrédient(s)', const Color(0xFFE3ECDB)),
            if (toLink > 0) ...[
              const SizedBox(width: 6),
              importPill('$toLink sans produit', const Color(0xFFF6EAD4)),
            ],
          ]),
          const SizedBox(height: 8),
          for (var i = 0; i < ingredients.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _ingredientCard(ingredients[i], i),
            ),
          OutlinedButton.icon(
            onPressed: () => setState(() => ingredients.add(RecipeIngredientDraft())),
            icon: const Icon(Icons.add, size: 18),
            label: const Text('Ajouter un ingrédient'),
          ),
          const SizedBox(height: 12),
          MockCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Étapes', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 3),
              const Text('Une étape par ligne.',
                  style: TextStyle(fontSize: 12, color: kMuted)),
              const SizedBox(height: 6),
              TextField(
                controller: _steps,
                maxLines: 8,
                minLines: 4,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Éplucher les légumes…',
                ),
              ),
            ]),
          ),
        ]),
      ),
      SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 6, 14, 10),
          child: Row(children: [
            Expanded(
              child: GradientButton(
                label: 'Enregistrer la fiche',
                onPressed: _saving ? null : _save,
                expand: true,
                loading: _saving,
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton(
              onPressed: () => setState(() => _ingredients = null),
              child: const Text('Refaire'),
            ),
          ]),
        ),
      ),
    ]);
  }

  Widget _ingredientCard(RecipeIngredientDraft ing, int index) {
    return MockCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: TextFormField(
              key: ValueKey('ing-name-$index-${ing.name.hashCode}'),
              initialValue: ing.name,
              onChanged: (v) => ing.name = v,
              decoration: const InputDecoration(isDense: true, labelText: 'Ingrédient'),
            ),
          ),
          IconButton(
            onPressed: () => setState(() => _ingredients!.removeAt(index)),
            icon: const Icon(Icons.delete_outline, size: 20),
            tooltip: 'Supprimer',
          ),
        ]),
        const SizedBox(height: 6),
        // Wrap et non Row : sur écran étroit les champs passent à la ligne au
        // lieu de déborder.
        Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
          importNumField('Qté', ing.qty, (v) => ing.qty = v, width: 80),
          SizedBox(
            width: 96,
            child: TextFormField(
              key: ValueKey('ing-unit-$index'),
              initialValue: ing.unit ?? '',
              onChanged: (v) => ing.unit = v,
              decoration: const InputDecoration(isDense: true, labelText: 'Unité'),
            ),
          ),
        ]),
        const SizedBox(height: 8),
        _productPicker(ing),
        if ((ing.productId ?? '').isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 4),
            child: Text(
              'Sans produit associé : la ligne n\'entrera pas dans le coût.',
              style: TextStyle(fontSize: 11.5, color: kWarn),
            ),
          )
        else if (ing.matchedName != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('Détecté : ${ing.matchedName}',
                style: const TextStyle(fontSize: 11.5, color: kMuted)),
          ),
      ]),
    );
  }

  Widget _productPicker(RecipeIngredientDraft ing) {
    final products = ref.watch(importProductsProvider);
    return products.when(
      loading: () => const SizedBox(height: 40, child: Center(child: LinearProgressIndicator())),
      error: (e, _) =>
          Text(apiErrorMessage(e), style: const TextStyle(fontSize: 11.5, color: kMuted)),
      data: (list) {
        final ids = list.map((p) => '${(p as Map)['id']}').toSet();
        final current = (ing.productId ?? '');
        return DropdownButtonFormField<String>(
          initialValue: ids.contains(current) ? current : '',
          isDense: true,
          isExpanded: true,
          decoration: const InputDecoration(isDense: true, labelText: 'Produit du catalogue'),
          items: [
            const DropdownMenuItem(value: '', child: Text('— aucun (produit à créer) —')),
            for (final p in list)
              DropdownMenuItem(
                value: '${(p as Map)['id']}',
                child: Text('${p['name']}', overflow: TextOverflow.ellipsis),
              ),
          ],
          onChanged: (v) => setState(() => ing.productId = (v ?? '').isEmpty ? null : v),
        );
      },
    );
  }
}
