import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../auth/auth_controller.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad;

/// Invoice detail + full line editing — the mobile equivalent of the web
/// `/factures/[id]` page (`frontend/src/features/invoices/invoice-detail.tsx`).
///
/// The mobile app could only create/import invoices; there was no way to open
/// one, see its lines, correct them, add/remove lines, map a product or delete
/// the invoice. This screen wires the SAME backend the web uses, action for
/// action, so the server recomputes prices and recipe costs exactly the same
/// way. See `backend/app/api/api_v1/endpoints/invoices.py`.
final invoiceDetailProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/invoices/$id');
  return Map<String, dynamic>.from(resp.data as Map);
});

final invoiceLinesProvider =
    FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/invoices/$id/lines');
  return (resp.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
});

/// Catalogue used to display line->product names and to power the map/create
/// dialogs (same role as the web `useProducts()`).
final _invoiceProductsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref
      .read(apiClientProvider)
      .dio
      .get('/products/enriched', queryParameters: {'limit': 500});
  return (resp.data as List);
});

/// Number like the web `formatNumber`: 3.0 -> "3", 2.5 -> "2,5", null -> "—".
String _num(dynamic v) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  if (n == null) return '$v';
  return n == n.roundToDouble() ? '${n.toInt()}' : n.toString().replaceAll('.', ',');
}

({String label, Color bg, Color fg}) _statusOf(Map<String, dynamic> inv) {
  final parsed = inv['parsed'] == true;
  final ocr = '${inv['ocr_status'] ?? ''}'.toLowerCase();
  if (parsed || ocr == 'done' || ocr == 'processed' || ocr == 'success') {
    return (label: 'Traitée', bg: const Color(0xFFE3ECDB), fg: kGood);
  }
  if (ocr == 'processing' || ocr == 'pending' || ocr == 'queued' || ocr == 'running') {
    return (label: 'OCR en cours', bg: const Color(0xFFE9E2D2), fg: const Color(0xFF8A7F70));
  }
  if (ocr == 'error' || ocr == 'failed') {
    return (label: 'Erreur', bg: const Color(0xFFF6E1DC), fg: const Color(0xFFB23A2E));
  }
  return (label: 'À vérifier', bg: const Color(0xFFF6EAD4), fg: kWarn);
}

class InvoiceDetailScreen extends ConsumerWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId, this.invoiceNumber});
  final String invoiceId;
  final String? invoiceNumber;

  bool _canWrite(WidgetRef ref) {
    final roles =
        (ref.watch(authControllerProvider).user?['roles'] as List?)?.cast<String>() ?? const [];
    return roles.contains('admin') || roles.contains('manager');
  }

  Future<void> _reload(WidgetRef ref) async {
    ref.invalidate(invoiceDetailProvider(invoiceId));
    ref.invalidate(invoiceLinesProvider(invoiceId));
    await ref.read(invoiceLinesProvider(invoiceId).future);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invoiceAsync = ref.watch(invoiceDetailProvider(invoiceId));
    final linesAsync = ref.watch(invoiceLinesProvider(invoiceId));
    final canWrite = _canWrite(ref);
    final productNames = <String, String>{
      for (final p in (ref.watch(_invoiceProductsProvider).valueOrNull ?? const []))
        '${p['id']}': '${p['name'] ?? ''}',
    };

    final title = invoiceAsync.valueOrNull?['invoice_number'] as String? ??
        invoiceNumber ??
        'Facture';

    return Scaffold(
      appBar: AppBar(
        title: Text(title.isEmpty ? 'Facture' : title,
            style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      floatingActionButton: (canWrite && linesAsync.hasValue)
          ? FloatingActionButton.extended(
              onPressed: () => _addLine(context, ref),
              icon: const Icon(Icons.add),
              label: const Text('Ligne'),
            )
          : null,
      body: RefreshIndicator(
        onRefresh: () => _reload(ref),
        child: invoiceAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _errorList(ref),
          data: (inv) {
            final st = _statusOf(inv);
            final lines = linesAsync.valueOrNull ?? const [];
            final needsReview = lines.where((l) => l['product_id'] == null).length;

            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
              children: [
                // --- En-tête facture ---
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                (inv['invoice_number'] as String?)?.isNotEmpty == true
                                    ? inv['invoice_number']
                                    : 'Facture sans numéro',
                                style: const TextStyle(
                                    fontFamily: 'Newsreader',
                                    fontSize: 18,
                                    fontWeight: FontWeight.w700),
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                              decoration: BoxDecoration(
                                  color: st.bg, borderRadius: BorderRadius.circular(999)),
                              child: Text(st.label,
                                  style: TextStyle(
                                      fontSize: 11, fontWeight: FontWeight.w600, color: st.fg)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${inv['date'] ?? 'Date inconnue'} · '
                          '${_money(inv['total_amount'], inv['currency'])}',
                          style: const TextStyle(fontSize: 13, color: kMuted),
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            OutlinedButton.icon(
                              onPressed: () => _openFile(context, ref),
                              icon: const Icon(Icons.description_outlined, size: 18),
                              label: const Text('Voir le fichier'),
                            ),
                            if (canWrite) ...[
                              OutlinedButton.icon(
                                onPressed: () => _reprocess(context, ref),
                                icon: const Icon(Icons.refresh, size: 18),
                                label: const Text('Re-traiter'),
                              ),
                              OutlinedButton.icon(
                                onPressed: () => _editInvoice(context, ref, inv),
                                icon: const Icon(Icons.edit_outlined, size: 18),
                                label: const Text('Modifier'),
                              ),
                              OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(foregroundColor: kBad),
                                onPressed: () => _deleteInvoice(context, ref),
                                icon: const Icon(Icons.delete_outline, size: 18),
                                label: const Text('Supprimer'),
                              ),
                            ],
                          ],
                        ),
                        if (needsReview > 0) ...[
                          const SizedBox(height: 12),
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF6EAD4),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.info_outline, size: 18, color: kWarn),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    '$needsReview ligne(s) à associer à un produit.',
                                    style: const TextStyle(fontSize: 12.5, color: Color(0xFF8A6D3B)),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 4),
                  child: Text('Lignes de la facture',
                      style: TextStyle(
                          fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
                ),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                  child: Text('Vérifiez, corrigez ou ajoutez des lignes.',
                      style: TextStyle(fontSize: 12, color: kMuted)),
                ),
                const SizedBox(height: 8),
                if (linesAsync.isLoading)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (lines.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 28),
                    child: Center(
                      child: Text('Aucune ligne extraite.',
                          style: TextStyle(color: kMuted)),
                    ),
                  )
                else
                  ...lines.map((line) => _LineCard(
                        line: line,
                        productName: line['product_id'] != null
                            ? productNames['${line['product_id']}']
                            : null,
                        canWrite: canWrite,
                        onEdit: () => _editLine(context, ref, line),
                        onMap: () => _mapProduct(context, ref, line),
                        onCreateProduct: () => _createProduct(context, ref, line),
                        onDelete: () => _deleteLine(context, ref, line),
                      )),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _errorList(WidgetRef ref) => ListView(children: [
        Padding(
          padding: const EdgeInsets.all(24),
          child: Column(children: [
            const Icon(Icons.cloud_off, size: 32, color: kMuted),
            const SizedBox(height: 10),
            const Text('Facture introuvable',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            FilledButton.icon(
                onPressed: () => _reload(ref),
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('Réessayer')),
          ]),
        ),
      ]);

  // --- Actions --------------------------------------------------------------

  Future<void> _openFile(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final resp = await ref.read(apiClientProvider).dio.get('/invoices/$invoiceId/file');
      final url = (resp.data as Map)['url'] as String?;
      if (url == null || url.isEmpty) {
        messenger.showSnackBar(
            const SnackBar(content: Text('Aucun fichier disponible pour cette facture.')));
        return;
      }
      final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
      if (!ok) {
        messenger.showSnackBar(const SnackBar(content: Text("Impossible d'ouvrir le fichier.")));
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _reprocess(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(content: Text('Re-traitement en cours…')));
    try {
      await ref.read(apiClientProvider).dio.post('/invoices/$invoiceId/process');
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Facture re-traitée.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _editInvoice(
      BuildContext context, WidgetRef ref, Map<String, dynamic> inv) async {
    final messenger = ScaffoldMessenger.of(context);
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _EditInvoiceDialog(invoice: inv),
    );
    if (result == null) return;
    try {
      await ref.read(apiClientProvider).dio.patch('/invoices/$invoiceId', data: result);
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Facture mise à jour.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _deleteInvoice(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Supprimer cette facture ?'),
        content: const Text(
            'La facture, ses lignes et les prix qui en découlent seront supprimés, '
            'et les coûts des recettes recalculés. Cette action est irréversible.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: kBad),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Supprimer')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(apiClientProvider).dio.delete('/invoices/$invoiceId');
      messenger.showSnackBar(const SnackBar(content: Text('Facture supprimée.')));
      navigator.pop(true); // back to the list, signal a refresh
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _addLine(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final fields = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const _LineDialog(),
    );
    if (fields == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/invoices/$invoiceId/lines', data: fields);
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Ligne ajoutée.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _editLine(
      BuildContext context, WidgetRef ref, Map<String, dynamic> line) async {
    final messenger = ScaffoldMessenger.of(context);
    final fields = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _LineDialog(line: line),
    );
    if (fields == null) return;
    try {
      await ref
          .read(apiClientProvider)
          .dio
          .patch('/invoices/$invoiceId/lines/${line['id']}', data: fields);
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Ligne enregistrée.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _deleteLine(
      BuildContext context, WidgetRef ref, Map<String, dynamic> line) async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Supprimer cette ligne ?'),
        content: Text('« ${line['description'] ?? '—'} »'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: kBad),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Supprimer')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref
          .read(apiClientProvider)
          .dio
          .delete('/invoices/$invoiceId/lines/${line['id']}');
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Ligne supprimée.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _mapProduct(
      BuildContext context, WidgetRef ref, Map<String, dynamic> line) async {
    final messenger = ScaffoldMessenger.of(context);
    final products = await ref.read(_invoiceProductsProvider.future);
    if (!context.mounted) return;
    final productId = await showDialog<String>(
      context: context,
      builder: (_) => _MapProductDialog(products: products, line: line),
    );
    if (productId == null) return;
    try {
      await ref.read(apiClientProvider).dio.post(
          '/invoices/$invoiceId/lines/${line['id']}/map-product',
          data: {'product_id': productId});
      ref.invalidate(_invoiceProductsProvider);
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Produit associé.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _createProduct(
      BuildContext context, WidgetRef ref, Map<String, dynamic> line) async {
    final messenger = ScaffoldMessenger.of(context);
    final fields = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _CreateProductDialog(line: line),
    );
    if (fields == null) return;
    try {
      await ref.read(apiClientProvider).dio.post(
          '/invoices/$invoiceId/lines/${line['id']}/create-product',
          data: fields);
      ref.invalidate(_invoiceProductsProvider);
      await _reload(ref);
      messenger.showSnackBar(const SnackBar(content: Text('Produit créé et associé.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }
}

String _money(dynamic total, dynamic currency) {
  final t = total is num ? total : num.tryParse('${total ?? ''}');
  if (t == null) return '—';
  if (currency == null || currency == 'EUR' || currency == '€') return eur(t);
  return '${t.toStringAsFixed(2).replaceAll('.', ',')} $currency';
}

// --------------------------------------------------------------------------- //
// Line card
// --------------------------------------------------------------------------- //
class _LineCard extends StatelessWidget {
  const _LineCard({
    required this.line,
    required this.productName,
    required this.canWrite,
    required this.onEdit,
    required this.onMap,
    required this.onCreateProduct,
    required this.onDelete,
  });
  final Map<String, dynamic> line;
  final String? productName;
  final bool canWrite;
  final VoidCallback onEdit;
  final VoidCallback onMap;
  final VoidCallback onCreateProduct;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final hasProduct = line['product_id'] != null;
    final conf = (line['match_confidence'] as num?)?.round();
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 8, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(line['description'] ?? '—',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(
              'Qté ${_num(line['qty'])}  ·  PU ${eur(line['unit_price'] as num?)}  ·  '
              'Total ${eur(line['line_total'] as num?)}',
              style: const TextStyle(fontSize: 12.5, color: kMuted),
            ),
            const SizedBox(height: 6),
            // Match cell
            if (!hasProduct)
              const Row(children: [
                Icon(Icons.warning_amber_rounded, size: 15, color: kWarn),
                SizedBox(width: 4),
                Text('À revoir', style: TextStyle(fontSize: 12.5, color: kWarn)),
              ])
            else
              Row(children: [
                const Icon(Icons.check_circle, size: 15, color: kGood),
                const SizedBox(width: 4),
                Flexible(
                  child: Text(productName ?? 'Produit associé',
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                ),
                if (conf != null) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 1),
                    decoration: BoxDecoration(
                      color: conf >= 80 ? const Color(0xFFE3ECDB) : const Color(0xFFF6EAD4),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text('$conf%',
                        style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: conf >= 80 ? kGood : kWarn)),
                  ),
                ],
              ]),
            if (canWrite)
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  IconButton(
                    icon: const Icon(Icons.edit_outlined, size: 20),
                    tooltip: 'Corriger',
                    onPressed: onEdit,
                  ),
                  IconButton(
                    icon: const Icon(Icons.link, size: 20),
                    tooltip: hasProduct ? 'Changer le produit' : 'Associer un produit',
                    onPressed: onMap,
                  ),
                  if (!hasProduct)
                    IconButton(
                      icon: const Icon(Icons.add_box_outlined, size: 20),
                      tooltip: 'Créer le produit',
                      onPressed: onCreateProduct,
                    ),
                  IconButton(
                    icon: const Icon(Icons.delete_outline, size: 20),
                    tooltip: 'Supprimer',
                    onPressed: onDelete,
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

// --------------------------------------------------------------------------- //
// Dialogs
// --------------------------------------------------------------------------- //

/// Add (line == null) or edit an invoice line: description, qty, unit, unit_price.
/// Mirrors the web `EditLineDialog` — `unit` is write-only (blank by default),
/// exactly like the web (the read model returns `unit_id`, not the code).
class _LineDialog extends StatefulWidget {
  const _LineDialog({this.line});
  final Map<String, dynamic>? line;

  @override
  State<_LineDialog> createState() => _LineDialogState();
}

class _LineDialogState extends State<_LineDialog> {
  late final TextEditingController _desc;
  late final TextEditingController _qty;
  late final TextEditingController _unit;
  late final TextEditingController _price;

  @override
  void initState() {
    super.initState();
    final l = widget.line;
    _desc = TextEditingController(text: l?['description']?.toString() ?? '');
    _qty = TextEditingController(text: l?['qty'] == null ? '' : _num(l!['qty']));
    _unit = TextEditingController(); // write-only, like the web
    _price = TextEditingController(
        text: l?['unit_price'] == null ? '' : '${l!['unit_price']}'.replaceAll('.', ','));
  }

  @override
  void dispose() {
    _desc.dispose();
    _qty.dispose();
    _unit.dispose();
    _price.dispose();
    super.dispose();
  }

  double? _parse(String s) => s.trim().isEmpty ? null : double.tryParse(s.replaceAll(',', '.'));

  @override
  Widget build(BuildContext context) {
    final isCreate = widget.line == null;
    return AlertDialog(
      title: Text(isCreate ? 'Ajouter une ligne' : 'Corriger la ligne'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _desc,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _qty,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Quantité'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _unit,
                    decoration: const InputDecoration(labelText: 'Unité', hintText: 'kg, g, l…'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _price,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Prix unitaire'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            final fields = <String, dynamic>{
              'description': _desc.text.trim().isEmpty ? null : _desc.text.trim(),
              'qty': _parse(_qty.text),
              'unit': _unit.text.trim().isEmpty ? null : _unit.text.trim(),
              'unit_price': _parse(_price.text),
            };
            Navigator.pop(context, fields);
          },
          child: Text(isCreate ? 'Ajouter' : 'Enregistrer'),
        ),
      ],
    );
  }
}

/// Edit invoice header: number, date, total, currency (web `EditInvoiceDialog`).
class _EditInvoiceDialog extends StatefulWidget {
  const _EditInvoiceDialog({required this.invoice});
  final Map<String, dynamic> invoice;

  @override
  State<_EditInvoiceDialog> createState() => _EditInvoiceDialogState();
}

class _EditInvoiceDialogState extends State<_EditInvoiceDialog> {
  late final TextEditingController _number;
  late final TextEditingController _date;
  late final TextEditingController _total;
  late final TextEditingController _currency;

  @override
  void initState() {
    super.initState();
    final inv = widget.invoice;
    _number = TextEditingController(text: inv['invoice_number']?.toString() ?? '');
    _date = TextEditingController(text: inv['date']?.toString() ?? '');
    _total = TextEditingController(
        text: inv['total_amount'] == null ? '' : '${inv['total_amount']}'.replaceAll('.', ','));
    _currency = TextEditingController(text: inv['currency']?.toString() ?? '');
  }

  @override
  void dispose() {
    _number.dispose();
    _date.dispose();
    _total.dispose();
    _currency.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Modifier la facture'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _number,
              decoration: const InputDecoration(labelText: 'N° de facture'),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _date,
                    decoration:
                        const InputDecoration(labelText: 'Date', hintText: 'AAAA-MM-JJ'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _currency,
                    decoration: const InputDecoration(labelText: 'Devise', hintText: 'EUR'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _total,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Montant total'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            Navigator.pop(context, <String, dynamic>{
              'invoice_number': _number.text.trim().isEmpty ? null : _number.text.trim(),
              'date': _date.text.trim().isEmpty ? null : _date.text.trim(),
              'total_amount': _total.text.trim().isEmpty
                  ? null
                  : double.tryParse(_total.text.replaceAll(',', '.')),
              'currency': _currency.text.trim().isEmpty ? null : _currency.text.trim(),
            });
          },
          child: const Text('Enregistrer'),
        ),
      ],
    );
  }
}

/// Search + pick a product to map to a line (web `MapProductDialog`).
class _MapProductDialog extends StatefulWidget {
  const _MapProductDialog({required this.products, required this.line});
  final List<dynamic> products;
  final Map<String, dynamic> line;

  @override
  State<_MapProductDialog> createState() => _MapProductDialogState();
}

class _MapProductDialogState extends State<_MapProductDialog> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final q = _q.trim().toLowerCase();
    final filtered = q.isEmpty
        ? widget.products
        : widget.products.where((p) {
            final name = '${p['name'] ?? ''}'.toLowerCase();
            final sku = '${p['sku'] ?? ''}'.toLowerCase();
            return name.contains(q) || sku.contains(q);
          }).toList();
    final currentId = widget.line['product_id'];

    return AlertDialog(
      title: const Text('Associer un produit'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Ligne : « ${widget.line['description'] ?? '—'} »',
                style: const TextStyle(fontSize: 12.5, color: kMuted)),
            const SizedBox(height: 8),
            TextField(
              autofocus: true,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: 'Rechercher un produit…',
                isDense: true,
              ),
              onChanged: (v) => setState(() => _q = v),
            ),
            const SizedBox(height: 8),
            SizedBox(
              height: 280,
              child: filtered.isEmpty
                  ? const Center(
                      child: Text('Aucun produit. Créez-en d\'abord dans « Produits ».',
                          textAlign: TextAlign.center, style: TextStyle(color: kMuted)))
                  : ListView(
                      shrinkWrap: true,
                      children: [
                        for (final p in filtered)
                          ListTile(
                            dense: true,
                            title: Text('${p['name'] ?? ''}'),
                            subtitle: (p['sku'] != null && '${p['sku']}'.isNotEmpty)
                                ? Text('${p['sku']}')
                                : null,
                            trailing: '${p['id']}' == '$currentId'
                                ? const Icon(Icons.check, color: kGood)
                                : null,
                            onTap: () => Navigator.pop(context, '${p['id']}'),
                          ),
                      ],
                    ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Fermer')),
      ],
    );
  }
}

/// Create a catalogue product from a line: name, sku (web `CreateProductDialog`).
class _CreateProductDialog extends StatefulWidget {
  const _CreateProductDialog({required this.line});
  final Map<String, dynamic> line;

  @override
  State<_CreateProductDialog> createState() => _CreateProductDialogState();
}

class _CreateProductDialogState extends State<_CreateProductDialog> {
  late final TextEditingController _name;
  final _sku = TextEditingController();

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.line['description']?.toString() ?? '');
  }

  @override
  void dispose() {
    _name.dispose();
    _sku.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Créer le produit'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Crée un produit du catalogue à partir de cette ligne, l\'associe et '
                'calcule son prix.',
                style: TextStyle(fontSize: 12.5, color: kMuted),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Nom du produit'),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _sku,
              decoration: const InputDecoration(labelText: 'Référence / SKU (optionnel)'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            if (_name.text.trim().isEmpty) return;
            Navigator.pop(context, <String, dynamic>{
              'name': _name.text.trim(),
              'sku': _sku.text.trim().isEmpty ? null : _sku.text.trim(),
            });
          },
          child: const Text('Créer et associer'),
        ),
      ],
    );
  }
}
