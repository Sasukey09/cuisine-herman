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
import 'invoice_detail_screen.dart';
import 'invoices_screen.dart' show invoiceFileTypes;

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
  List<ImportLine>? _lines;
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
      final lines = _lines!.map((l) => l.toConfirmJson()).toList();
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

  Widget _reviewView(List<ImportLine> lines) {
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
            importPill('$toAssoc à associer', const Color(0xFFE3ECDB)),
            const SizedBox(width: 6),
            importPill('$toCreate à créer', const Color(0xFFF6EAD4)),
          ]),
          const SizedBox(height: 8),
          for (final l in lines)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: ImportLineCard(line: l, onChanged: () => setState(() {})),
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
            OutlinedButton(onPressed: () => setState(() => _lines = null), child: const Text('Refaire')),
          ]),
        ),
      ),
    ]);
  }

}
