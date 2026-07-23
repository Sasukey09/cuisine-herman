import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kWarn, kProductCategories;

/// Éditeur de ligne partagé entre l'import de FACTURE et l'import de DEVIS.
///
/// Les deux imports posent la même question pour chaque ligne détectée : « ce
/// libellé, c'est quel produit — un existant, un nouveau, ou on ignore ? ».
/// Cette logique vivait dans l'écran facture ; elle est ici pour être partagée
/// plutôt que recopiée (le devis y ajoute remise et conditionnement via
/// `extraFields`).

/// Catalogue produits pour le sélecteur « associer ».
final importProductsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref
      .read(apiClientProvider)
      .dio
      .get('/products/enriched', queryParameters: {'limit': 500});
  return (resp.data as List?) ?? const [];
});

class ImportLine {
  ImportLine({
    required this.description,
    this.qty,
    this.unit,
    this.unitPrice,
    this.vat,
    this.lineTotal,
    required this.action,
    this.category = '',
    this.productId = '',
    this.matchedName,
    this.confidence,
    this.needsReview = true,
    this.discountPct,
    this.packSize,
  });

  String description;
  num? qty;
  String? unit;
  num? unitPrice;
  num? vat;
  num? lineTotal;
  String action; // create | associate | skip
  String category;
  String productId;
  String? matchedName;
  num? confidence;
  bool needsReview;
  // Propres au devis (restent nuls sur une facture).
  num? discountPct;
  String? packSize;

  /// Depuis une ligne d'aperçu OCR (`/invoices/preview` ou `/quotes/preview`).
  factory ImportLine.fromPreview(Map<String, dynamic> m) {
    final matched = m['matched_product_id'] != null;
    final review = m['needs_review'] == true || !matched;
    return ImportLine(
      description: '${m['description'] ?? ''}',
      qty: m['qty'] as num?,
      unit: m['unit'] as String?,
      unitPrice: m['unit_price'] as num?,
      vat: m['vat_rate'] as num?,
      lineTotal: m['line_total'] as num?,
      discountPct: m['discount_pct'] as num?,
      packSize: m['pack_size'] as String?,
      action: (!review && matched) ? 'associate' : 'create',
      category: '${m['suggested_category'] ?? ''}',
      productId: '${m['matched_product_id'] ?? ''}',
      matchedName: m['matched_product_name'] as String?,
      confidence: m['match_confidence'] as num?,
      needsReview: review,
    );
  }

  /// Corps envoyé à `/…/confirm`. Les champs propres au devis ne sont inclus
  /// que s'ils sont renseignés : inutile de les envoyer à l'API facture.
  Map<String, dynamic> toConfirmJson() => {
        'description': description,
        'qty': qty,
        'unit': unit,
        'unit_price': unitPrice,
        'line_total': lineTotal,
        'vat_rate': vat,
        if (discountPct != null) 'discount_pct': discountPct,
        if (packSize != null && packSize!.isNotEmpty) 'pack_size': packSize,
        'action': action,
        'product_id': action == 'associate' ? (productId.isEmpty ? null : productId) : null,
        'category': action == 'create' ? (category.isEmpty ? null : category) : null,
      };
}

/// Pastille de comptage ("3 à créer").
Widget importPill(String label, Color bg) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
    );

/// Champ numérique compact réutilisable (Qté, PU, TVA, remise…).
Widget importNumField(
  String label,
  num? value,
  void Function(num?) onChanged, {
  required double width,
}) {
  return SizedBox(
    width: width,
    child: TextFormField(
      initialValue: value != null ? '$value' : '',
      keyboardType: TextInputType.number,
      onChanged: (v) =>
          onChanged(v.trim().isEmpty ? null : num.tryParse(v.replaceAll(',', '.'))),
      decoration: InputDecoration(isDense: true, labelText: label),
    ),
  );
}

/// La carte d'édition d'une ligne détectée.
class ImportLineCard extends ConsumerWidget {
  const ImportLineCard({
    super.key,
    required this.line,
    required this.onChanged,
    this.extraFields = const [],
  });

  final ImportLine line;

  /// Appelé quand un choix impose un rebuild du parent (action, produit).
  final VoidCallback onChanged;

  /// Champs propres au document (devis : remise, conditionnement).
  final List<Widget> extraFields;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MockCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        TextFormField(
          initialValue: line.description,
          onChanged: (v) => line.description = v,
          decoration: const InputDecoration(isDense: true, labelText: 'Désignation'),
        ),
        const SizedBox(height: 6),
        // Wrap (et pas Row) : les petits champs passent à la ligne sur écran
        // étroit au lieu de déborder.
        Wrap(spacing: 6, runSpacing: 6, children: [
          importNumField('Qté', line.qty, (v) => line.qty = v, width: 70),
          SizedBox(
            width: 92,
            child: TextFormField(
              initialValue: line.unit ?? '',
              onChanged: (v) => line.unit = v,
              decoration: const InputDecoration(isDense: true, labelText: 'Unité'),
            ),
          ),
          importNumField('PU', line.unitPrice, (v) => line.unitPrice = v, width: 84),
          // 92 (et non 74) : à 74 le libellé « TVA % » s'affichait « TV… ».
          importNumField('TVA %', line.vat, (v) => line.vat = v, width: 92),
          ...extraFields,
        ]),
        const SizedBox(height: 8),
        Row(children: [
          SizedBox(
            width: 150,
            child: DropdownButtonFormField<String>(
              initialValue: line.action,
              isDense: true,
              isExpanded: true, // ellipse plutôt que débordement
              decoration: const InputDecoration(isDense: true),
              items: const [
                DropdownMenuItem(value: 'create', child: Text('Créer')),
                DropdownMenuItem(value: 'associate', child: Text('Associer')),
                DropdownMenuItem(value: 'skip', child: Text('Ignorer')),
              ],
              onChanged: (v) {
                line.action = v ?? 'create';
                onChanged();
              },
            ),
          ),
          const SizedBox(width: 8),
          if (line.action == 'create') Expanded(child: _categoryPicker()),
          if (line.action == 'associate') Expanded(child: _productPicker(ref)),
        ]),
        if (line.action == 'associate' && line.matchedName != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              'Suggéré : ${line.matchedName}'
              '${line.confidence != null ? ' (${line.confidence!.round()}%)' : ''}',
              style: const TextStyle(fontSize: 11.5, color: kMuted),
            ),
          ),
        if (line.action == 'create' && line.needsReview)
          const Padding(
            padding: EdgeInsets.only(top: 4),
            child: Text('nouveau produit', style: TextStyle(fontSize: 11.5, color: kWarn)),
          ),
      ]),
    );
  }

  Widget _categoryPicker() {
    final values = <String>['', ...kProductCategories];
    return DropdownButtonFormField<String>(
      initialValue: values.contains(line.category) ? line.category : '',
      isDense: true,
      isExpanded: true,
      decoration: const InputDecoration(isDense: true),
      items: [
        const DropdownMenuItem(value: '', child: Text('Catégorie auto')),
        for (final c in kProductCategories) DropdownMenuItem(value: c, child: Text(c)),
      ],
      onChanged: (v) => line.category = v ?? '',
    );
  }

  Widget _productPicker(WidgetRef ref) {
    final products = ref.watch(importProductsProvider);
    return products.when(
      loading: () => const SizedBox(height: 40, child: Center(child: LinearProgressIndicator())),
      error: (e, _) =>
          Text(apiErrorMessage(e), style: const TextStyle(fontSize: 11.5, color: kMuted)),
      data: (list) {
        final ids = list.map((p) => '${(p as Map)['id']}').toList();
        return DropdownButtonFormField<String>(
          initialValue: ids.contains(line.productId) ? line.productId : null,
          isDense: true,
          isExpanded: true,
          decoration: const InputDecoration(isDense: true, hintText: 'Produit…'),
          items: [
            for (final p in list)
              DropdownMenuItem(
                value: '${(p as Map)['id']}',
                child: Text('${p['name']}', overflow: TextOverflow.ellipsis),
              ),
          ],
          onChanged: (v) {
            line.productId = v ?? '';
            onChanged();
          },
        );
      },
    );
  }
}
