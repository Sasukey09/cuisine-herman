import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted;
import '../imports/import_line_editor.dart';
import '../invoices/invoices_screen.dart' show invoiceFileTypes;
import 'quote_detail_screen.dart';
import 'quotes_screen.dart' show quotesListProvider;

/// Import de devis mobile — équivalent du `/devis/import` web : aperçu OCR,
/// puis par ligne créer / associer / ignorer, avec en plus les champs propres
/// au devis (validité, remise, conditions, conditionnement).
///
/// Réutilise `invoiceFileTypes` (mêmes formats acceptés — dont les UTI iOS
/// obligatoires) et `ImportLineCard` (éditeur de ligne partagé).
class QuoteSmartImportScreen extends ConsumerStatefulWidget {
  const QuoteSmartImportScreen({super.key});
  @override
  ConsumerState<QuoteSmartImportScreen> createState() => _State();
}

class _State extends ConsumerState<QuoteSmartImportScreen> {
  final _supplier = TextEditingController();
  final _number = TextEditingController();
  final _conditions = TextEditingController();
  final _discount = TextEditingController();
  String? _date;
  String? _validUntil;
  List<ImportLine>? _lines;
  bool _loading = false;
  bool _saving = false;

  @override
  void dispose() {
    _supplier.dispose();
    _number.dispose();
    _conditions.dispose();
    _discount.dispose();
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
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: file.name),
      });
      final resp = await ref.read(apiClientProvider).dio.post(
            '/quotes/preview',
            data: form,
            options: Options(
              sendTimeout: const Duration(seconds: 120),
              receiveTimeout: const Duration(seconds: 120),
            ),
          );
      final data = Map<String, dynamic>.from(resp.data as Map);
      _supplier.text = '${data['supplier'] ?? ''}';
      _number.text = '${data['quote_number'] ?? ''}';
      _conditions.text = '${data['conditions'] ?? ''}';
      _discount.text = data['discount_total'] == null ? '' : '${data['discount_total']}';
      _date = data['date'] as String?;
      _validUntil = data['valid_until'] as String?;
      setState(() {
        _lines = ((data['lines'] as List?) ?? const [])
            .map((e) => ImportLine.fromPreview(Map<String, dynamic>.from(e as Map)))
            .toList();
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
      final resp = await ref.read(apiClientProvider).dio.post('/quotes/confirm', data: {
        'supplier': _supplier.text.trim().isEmpty ? null : _supplier.text.trim(),
        'quote_number': _number.text.trim().isEmpty ? null : _number.text.trim(),
        'date': _date,
        'valid_until': _validUntil,
        'conditions': _conditions.text.trim().isEmpty ? null : _conditions.text.trim(),
        'discount_total': _discount.text.trim().isEmpty
            ? null
            : num.tryParse(_discount.text.replaceAll(',', '.')),
        'currency': 'EUR',
        'lines': _lines!.map((l) => l.toConfirmJson()).toList(),
      });
      final data = Map<String, dynamic>.from(resp.data as Map);
      ref.invalidate(quotesListProvider);
      messenger.showSnackBar(SnackBar(
        content: Text('Devis ${data['reference'] ?? ''} importé — '
            '${data['lines']} ligne(s), ${data['created_products']} produit(s) créé(s).'),
      ));
      navigator.pushReplacement(MaterialPageRoute(
        builder: (_) => QuoteDetailScreen(
          quoteId: '${data['quote_id']}',
          reference: data['reference'] as String?,
        ),
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
      appBar: AppBar(
        title: const Text('Import de devis', style: TextStyle(fontFamily: 'Newsreader')),
      ),
      body: lines == null ? _pickView() : _reviewView(lines),
    );
  }

  Widget _pickView() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        const Text('📄', style: TextStyle(fontSize: 34)),
        const SizedBox(height: 8),
        const Text(
          'Importez le devis du fournisseur',
          textAlign: TextAlign.center,
          style: TextStyle(fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 6),
        const Text(
          "L'OCR lit le devis, suggère les produits (existants ou à créer) et leur "
          'catégorie. Les prix restent propres au devis : ils n\'entrent pas dans '
          "l'historique d'achat.",
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 13, color: kMuted),
        ),
        const SizedBox(height: 20),
        SizedBox(
          width: double.infinity,
          child: GradientButton(
            label: 'Choisir un devis (PDF / photo)',
            onPressed: _loading ? null : _pickAndPreview,
            expand: true,
            loading: _loading,
          ),
        ),
      ]),
    );
  }

  Widget _reviewView(List<ImportLine> lines) {
    final toCreate = lines.where((l) => l.action == 'create').length;
    final toAssoc = lines.where((l) => l.action == 'associate').length;
    return Column(children: [
      Expanded(
        child: ListView(padding: const EdgeInsets.all(14), children: [
          MockCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Devis détecté', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              TextField(
                controller: _supplier,
                decoration: const InputDecoration(labelText: 'Fournisseur'),
              ),
              TextField(
                controller: _number,
                decoration: const InputDecoration(labelText: 'N° de devis'),
              ),
              const SizedBox(height: 6),
              Text(
                [
                  if (_date != null) 'Date : $_date',
                  if (_validUntil != null) 'Valable jusqu\'au $_validUntil',
                ].join('   ·   '),
                style: const TextStyle(fontSize: 12, color: kMuted),
              ),
              const SizedBox(height: 6),
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _discount,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Remise globale (€)'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: TextField(
                    controller: _conditions,
                    decoration: const InputDecoration(labelText: 'Conditions'),
                  ),
                ),
              ]),
            ]),
          ),
          const SizedBox(height: 8),
          Row(children: [
            importPill('$toAssoc à associer', const Color(0xFFE3ECDB)),
            const SizedBox(width: 6),
            importPill('$toCreate à créer', const Color(0xFFF6EAD4)),
          ]),
          const SizedBox(height: 8),
          for (final l in lines)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: ImportLineCard(
                line: l,
                onChanged: () => setState(() {}),
                extraFields: [
                  importNumField('Rem. %', l.discountPct, (v) => l.discountPct = v, width: 96),
                  SizedBox(
                    width: 120,
                    child: TextFormField(
                      initialValue: l.packSize ?? '',
                      onChanged: (v) => l.packSize = v,
                      decoration: const InputDecoration(isDense: true, labelText: 'Condit.'),
                    ),
                  ),
                ],
              ),
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
                label: 'Valider et importer',
                onPressed: _saving ? null : _confirm,
                expand: true,
                loading: _saving,
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton(
              onPressed: () => setState(() => _lines = null),
              child: const Text('Refaire'),
            ),
          ]),
        ),
      ),
    ]);
  }
}
