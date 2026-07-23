import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../auth/auth_controller.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kTerracotta;
import 'quote_detail_screen.dart';
import 'quote_matrix_screen.dart';
import 'quote_smart_import_screen.dart';

/// Comparateur de devis (#1) — liste + création. Un devis = un panier de
/// produits chiffré par fournisseur (voir `quote_detail_screen.dart`).
final quotesListProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/quotes/');
  return (resp.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
});

/// Catalogue produits pour les sélecteurs des dialogues (création / ajout ligne).
final quoteProductsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref
      .read(apiClientProvider)
      .dio
      .get('/products/enriched', queryParameters: {'limit': 500});
  return (resp.data as List);
});

({String label, Color bg, Color fg}) statusOf(String? s) {
  switch (s) {
    case 'ordered':
      return (label: 'Commandé', bg: const Color(0xFFE3ECDB), fg: kGood);
    case 'archived':
      return (label: 'Archivé', bg: const Color(0xFFECE6DA), fg: kMuted);
    default:
      return (label: 'Brouillon', bg: const Color(0xFFF6EAD4), fg: kWarn);
  }
}

class QuotesScreen extends ConsumerWidget {
  const QuotesScreen({super.key});

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final products = await ref.read(quoteProductsProvider.future);
    if (!context.mounted) return;
    final payload = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _CreateQuoteDialog(products: products),
    );
    if (payload == null) return;
    try {
      final resp =
          await ref.read(apiClientProvider).dio.post('/quotes/', data: payload);
      ref.invalidate(quotesListProvider);
      final quote = Map<String, dynamic>.from(resp.data as Map);
      messenger.showSnackBar(
          SnackBar(content: Text('Devis ${quote['reference'] ?? ''} créé.')));
      if (context.mounted) {
        await Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => QuoteDetailScreen(
            quoteId: '${quote['id']}',
            reference: quote['reference'] as String?,
          ),
        ));
        ref.invalidate(quotesListProvider);
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canWrite = ref.watch(canWriteProvider);
    final quotesAsync = ref.watch(quotesListProvider);

    return Scaffold(
      floatingActionButton:
          canWrite ? GradientFab(onPressed: () => _create(context, ref)) : null,
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(quotesListProvider);
          await ref.read(quotesListProvider.future);
        },
        child: quotesAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(children: [
                const Icon(Icons.cloud_off, size: 32, color: kMuted),
                const SizedBox(height: 10),
                Text(apiErrorMessage(e), textAlign: TextAlign.center),
              ]),
            ),
          ]),
          data: (quotes) {
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
              children: [
                if (canWrite) _importBanner(context, ref),
                if (quotes.isEmpty) ...[
                  const SizedBox(height: 80),
                  const Icon(Icons.description_outlined, size: 40, color: kMuted),
                  const SizedBox(height: 12),
                  const Center(
                    child: Text(
                      'Aucun devis. Importez celui d\'un fournisseur,\nou touchez + pour comparer un panier.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: kMuted),
                    ),
                  ),
                ] else
                  for (final q in quotes) _QuoteCard(quote: q),
              ],
            );
          },
        ),
      ),
    );
  }
}

/// Point d'entrée de l'import OCR — le devis n'est plus seulement saisi à la
/// main, il s'importe comme une facture.
Widget _importBanner(BuildContext context, WidgetRef ref) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: MockCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Importer un devis',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        const SizedBox(height: 3),
        const Text("PDF ou photo — l'OCR extrait les lignes.",
            style: TextStyle(fontSize: 12, color: kMuted)),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () async {
                await Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => const QuoteSmartImportScreen(),
                ));
                ref.invalidate(quotesListProvider);
              },
              icon: const Icon(Icons.upload_file, size: 18, color: kTerracotta),
              label: const Text('Choisir un fichier'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const QuoteMatrixScreen(),
              )),
              icon: const Icon(Icons.table_chart_outlined, size: 18, color: kTerracotta),
              label: const Text('Comparatif'),
            ),
          ),
        ]),
      ]),
    ),
  );
}

class _QuoteCard extends StatelessWidget {
  const _QuoteCard({required this.quote});
  final Map<String, dynamic> quote;

  @override
  Widget build(BuildContext context) {
    final st = statusOf(quote['status'] as String?);
    final title = (quote['title'] as String?)?.trim();
    final total = quote['total_amount'] as num?;
    final lineCount = quote['line_count'] as int?;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: MockCard(
        onTap: () => Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => QuoteDetailScreen(
            quoteId: '${quote['id']}',
            reference: quote['reference'] as String?,
          ),
        )),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title?.isNotEmpty == true ? title! : '${quote['reference'] ?? 'Devis'}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                  decoration:
                      BoxDecoration(color: st.bg, borderRadius: BorderRadius.circular(999)),
                  child: Text(st.label,
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: st.fg)),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(
                  child: Text(
                    [
                      '${quote['reference'] ?? ''}',
                      if (lineCount != null) '$lineCount ligne${lineCount == 1 ? '' : 's'}',
                      if (quote['supplier_name'] != null) '${quote['supplier_name']}',
                    ].where((s) => s.isNotEmpty).join('  ·  '),
                    style: const TextStyle(fontSize: 12.5, color: kMuted),
                  ),
                ),
                if (total != null)
                  Text(eur(total),
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Création d'un devis : intitulé + panier de produits (produit + quantité).
class _CreateQuoteDialog extends StatefulWidget {
  const _CreateQuoteDialog({required this.products});
  final List<dynamic> products;

  @override
  State<_CreateQuoteDialog> createState() => _CreateQuoteDialogState();
}

class _CreateQuoteDialogState extends State<_CreateQuoteDialog> {
  final _title = TextEditingController();
  final List<_DraftLine> _lines = [_DraftLine()];

  @override
  void dispose() {
    _title.dispose();
    for (final l in _lines) {
      l.qty.dispose();
    }
    super.dispose();
  }

  double? _parseQty(String s) =>
      s.trim().isEmpty ? null : double.tryParse(s.replaceAll(',', '.'));

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Nouveau devis'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _title,
              decoration: const InputDecoration(labelText: 'Intitulé (optionnel)'),
            ),
            const SizedBox(height: 12),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text('Produits à comparer',
                  style: TextStyle(fontSize: 12.5, color: kMuted)),
            ),
            const SizedBox(height: 6),
            for (int i = 0; i < _lines.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        // ignore: deprecated_member_use
                        value: _lines[i].productId,
                        isExpanded: true,
                        decoration: const InputDecoration(labelText: 'Produit', isDense: true),
                        items: [
                          for (final p in widget.products)
                            DropdownMenuItem(
                              value: '${p['id']}',
                              child: Text('${p['name'] ?? ''}',
                                  maxLines: 1, overflow: TextOverflow.ellipsis),
                            ),
                        ],
                        onChanged: (v) => setState(() => _lines[i].productId = v),
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 68,
                      child: TextField(
                        controller: _lines[i].qty,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'Qté', isDense: true),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 18),
                      onPressed: _lines.length == 1
                          ? null
                          : () => setState(() => _lines.removeAt(i)),
                    ),
                  ],
                ),
              ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => setState(() => _lines.add(_DraftLine())),
                icon: const Icon(Icons.add, size: 18, color: kTerracotta),
                label: const Text('Ajouter un produit'),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            final lines = [
              for (final l in _lines)
                if (l.productId != null)
                  {'product_id': l.productId, 'qty': _parseQty(l.qty.text)},
            ];
            if (lines.isEmpty) return;
            Navigator.pop(context, {
              'title': _title.text.trim().isEmpty ? null : _title.text.trim(),
              'lines': lines,
            });
          },
          child: const Text('Créer'),
        ),
      ],
    );
  }
}

class _DraftLine {
  String? productId;
  final TextEditingController qty = TextEditingController();
}
