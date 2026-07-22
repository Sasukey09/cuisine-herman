import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kWarn, kProductCategories;
import 'invoice_detail_screen.dart';
import 'invoices_screen.dart' show invoiceFileTypes;

/// Products for the "associate" picker.
final _productsForImportProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/products/enriched', queryParameters: {'limit': 500});
  return (resp.data as List?) ?? const [];
});

class _Line {
  _Line({
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
}

/// Mobile smart invoice import — the equivalent of the web `/factures/import`
/// validation dialog: OCR preview + per-line create/associate/skip + edit
/// TVA/category, then confirm.
class InvoiceSmartImportScreen extends ConsumerStatefulWidget {
  const InvoiceSmartImportScreen({super.key});
  @override
  ConsumerState<InvoiceSmartImportScreen> createState() => _State();
}

class _State extends ConsumerState<InvoiceSmartImportScreen> {
  final _supplier = TextEditingController();
  final _number = TextEditingController();
  String? _date;
  List<_Line>? _lines;
  bool _loading = false;
  bool _saving = false;

  @override
  void dispose() {
    _supplier.dispose();
    _number.dispose();
    super.dispose();
  }

  Future<void> _pickAndPreview() async {
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
      final form = FormData.fromMap({'file': MultipartFile.fromBytes(bytes, filename: file.name)});
      final resp = await ref.read(apiClientProvider).dio.post(
            '/invoices/preview',
            data: form,
            options: Options(sendTimeout: const Duration(seconds: 120), receiveTimeout: const Duration(seconds: 120)),
          );
      final data = Map<String, dynamic>.from(resp.data as Map);
      _supplier.text = '${data['supplier'] ?? ''}';
      _number.text = '${data['invoice_number'] ?? ''}';
      _date = data['date'] as String?;
      setState(() {
        _lines = ((data['lines'] as List?) ?? const []).map((e) {
          final m = Map<String, dynamic>.from(e as Map);
          final matched = m['matched_product_id'] != null;
          final review = m['needs_review'] == true || !matched;
          return _Line(
            description: '${m['description'] ?? ''}',
            qty: m['qty'] as num?,
            unit: m['unit'] as String?,
            unitPrice: m['unit_price'] as num?,
            vat: m['vat_rate'] as num?,
            lineTotal: m['line_total'] as num?,
            action: (!review && matched) ? 'associate' : 'create',
            category: '${m['suggested_category'] ?? ''}',
            productId: '${m['matched_product_id'] ?? ''}',
            matchedName: m['matched_product_name'] as String?,
            confidence: m['match_confidence'] as num?,
            needsReview: review,
          );
        }).toList();
      });
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _confirm() async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    setState(() => _saving = true);
    try {
      final lines = _lines!.map((l) => {
            'description': l.description,
            'qty': l.qty,
            'unit': l.unit,
            'unit_price': l.unitPrice,
            'line_total': l.lineTotal,
            'vat_rate': l.vat,
            'action': l.action,
            'product_id': l.action == 'associate' ? (l.productId.isEmpty ? null : l.productId) : null,
            'category': l.action == 'create' ? (l.category.isEmpty ? null : l.category) : null,
          }).toList();
      final resp = await ref.read(apiClientProvider).dio.post('/invoices/confirm', data: {
        'supplier': _supplier.text.trim().isEmpty ? null : _supplier.text.trim(),
        'invoice_number': _number.text.trim().isEmpty ? null : _number.text.trim(),
        'date': _date,
        'currency': 'EUR',
        'lines': lines,
      });
      final invId = (resp.data as Map)['invoice_id'] as String;
      messenger.showSnackBar(const SnackBar(content: Text('Facture importée et enregistrée.')));
      navigator.pushReplacement(MaterialPageRoute(
        builder: (_) => InvoiceDetailScreen(invoiceId: invId, invoiceNumber: _number.text.trim()),
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final lines = _lines;
    return Scaffold(
      appBar: AppBar(title: const Text('Import intelligent', style: TextStyle(fontFamily: 'Newsreader'))),
      body: lines == null ? _pickView() : _reviewView(lines),
    );
  }

  Widget _pickView() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        const Text('🧾', style: TextStyle(fontSize: 34)),
        const SizedBox(height: 8),
        const Text('Vérifiez avant d\'enregistrer',
            textAlign: TextAlign.center,
            style: TextStyle(fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        const Text(
          "L'OCR détecte les lignes, suggère les produits (existants ou à créer) et leur catégorie. "
          'Les produits inexistants seront créés avec TVA + catégorie et reliés au fournisseur.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 13, color: kMuted),
        ),
        const SizedBox(height: 20),
        SizedBox(
          width: double.infinity,
          child: GradientButton(
            label: 'Choisir une facture (PDF / photo)',
            onPressed: _loading ? null : _pickAndPreview,
            expand: true,
            loading: _loading,
          ),
        ),
      ]),
    );
  }

  Widget _reviewView(List<_Line> lines) {
    final toCreate = lines.where((l) => l.action == 'create').length;
    final toAssoc = lines.where((l) => l.action == 'associate').length;
    return Column(children: [
      Expanded(
        child: ListView(padding: const EdgeInsets.all(14), children: [
          MockCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Facture détectée', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              TextField(controller: _supplier, decoration: const InputDecoration(labelText: 'Fournisseur')),
              TextField(controller: _number, decoration: const InputDecoration(labelText: 'N° facture')),
            ]),
          ),
          const SizedBox(height: 8),
          Row(children: [
            _pill('$toAssoc à associer', const Color(0xFFE3ECDB)),
            const SizedBox(width: 6),
            _pill('$toCreate à créer', const Color(0xFFF6EAD4)),
          ]),
          const SizedBox(height: 8),
          for (var i = 0; i < lines.length; i++) _lineCard(lines[i], i),
        ]),
      ),
      SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 6, 14, 10),
          child: Row(children: [
            Expanded(
              child: GradientButton(
                label: 'Valider et importer',
                onPressed: _saving ? null : _confirm,
                expand: true,
                loading: _saving,
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton(onPressed: () => setState(() => _lines = null), child: const Text('Refaire')),
          ]),
        ),
      ),
    ]);
  }

  Widget _pill(String t, Color bg) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
        child: Text(t, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
      );

  Widget _lineCard(_Line l, int i) {
    return MockCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        TextFormField(
          initialValue: l.description,
          onChanged: (v) => l.description = v,
          decoration: const InputDecoration(isDense: true, labelText: 'Désignation'),
        ),
        const SizedBox(height: 6),
        // Wrap (not Row) so the four small fields flow to a second line on narrow
        // screens instead of overflowing.
        Wrap(spacing: 6, runSpacing: 6, children: [
          _numField('Qté', l.qty, (v) => l.qty = v, width: 70),
          SizedBox(
            width: 92,
            child: TextFormField(
              initialValue: l.unit ?? '',
              onChanged: (v) => l.unit = v,
              decoration: const InputDecoration(isDense: true, labelText: 'Unité'),
            ),
          ),
          _numField('PU', l.unitPrice, (v) => l.unitPrice = v, width: 84),
          _numField('TVA%', l.vat, (v) => l.vat = v, width: 74),
        ]),
        const SizedBox(height: 8),
        Row(children: [
          SizedBox(
            width: 128,
            child: DropdownButtonFormField<String>(
              initialValue: l.action,
              isDense: true,
              decoration: const InputDecoration(isDense: true),
              items: const [
                DropdownMenuItem(value: 'create', child: Text('➕ Créer')),
                DropdownMenuItem(value: 'associate', child: Text('🔗 Associer')),
                DropdownMenuItem(value: 'skip', child: Text('Ignorer')),
              ],
              onChanged: (v) => setState(() => l.action = v ?? 'create'),
            ),
          ),
          const SizedBox(width: 8),
          if (l.action == 'create') Expanded(child: _categoryPicker(l)),
          if (l.action == 'associate') Expanded(child: _productPicker(l)),
        ]),
        if (l.action == 'associate' && l.matchedName != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('Suggéré : ${l.matchedName}'
                '${l.confidence != null ? ' (${l.confidence!.round()}%)' : ''}',
                style: const TextStyle(fontSize: 11.5, color: kMuted)),
          ),
        if (l.action == 'create' && l.needsReview)
          const Padding(
            padding: EdgeInsets.only(top: 4),
            child: Text('nouveau produit', style: TextStyle(fontSize: 11.5, color: kWarn)),
          ),
      ]),
    );
  }

  Widget _numField(String label, num? value, void Function(num?) onChanged, {required double width}) {
    return SizedBox(
      width: width,
      child: TextFormField(
        initialValue: value != null ? '$value' : '',
        keyboardType: TextInputType.number,
        onChanged: (v) => onChanged(v.trim().isEmpty ? null : num.tryParse(v.replaceAll(',', '.'))),
        decoration: InputDecoration(isDense: true, labelText: label),
      ),
    );
  }

  Widget _categoryPicker(_Line l) {
    final values = <String>['', ...kProductCategories];
    return DropdownButtonFormField<String>(
      initialValue: values.contains(l.category) ? l.category : '',
      isDense: true,
      isExpanded: true,
      decoration: const InputDecoration(isDense: true),
      items: [
        const DropdownMenuItem(value: '', child: Text('Catégorie auto')),
        for (final c in kProductCategories) DropdownMenuItem(value: c, child: Text(c)),
      ],
      onChanged: (v) => l.category = v ?? '',
    );
  }

  Widget _productPicker(_Line l) {
    final products = ref.watch(_productsForImportProvider);
    return products.when(
      loading: () => const SizedBox(height: 40, child: Center(child: LinearProgressIndicator())),
      error: (e, _) => Text(apiErrorMessage(e), style: const TextStyle(fontSize: 11.5, color: kMuted)),
      data: (list) {
        final ids = list.map((p) => '${(p as Map)['id']}').toList();
        return DropdownButtonFormField<String>(
          initialValue: ids.contains(l.productId) ? l.productId : null,
          isDense: true,
          isExpanded: true,
          decoration: const InputDecoration(isDense: true, hintText: 'Produit…'),
          items: [
            for (final p in list)
              DropdownMenuItem(value: '${(p as Map)['id']}', child: Text('${p['name']}', overflow: TextOverflow.ellipsis)),
          ],
          onChanged: (v) => setState(() => l.productId = v ?? ''),
        );
      },
    );
  }
}
