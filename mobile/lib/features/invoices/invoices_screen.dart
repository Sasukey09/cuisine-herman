import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kTerracotta;
import 'invoice_detail_screen.dart';
import 'invoice_smart_import_screen.dart';

final _invoicesProvider = FutureProvider.autoDispose<Loaded>((ref) async {
  return fetchWithCache(ref, cacheKey: 'invoices', request: () async {
    final resp = await ref.read(apiClientProvider).dio.get('/invoices/');
    return resp.data;
  });
});

/// PDF or photo of an invoice.
/// - `extensions` + `mimeTypes` are what Android's file dialog and the
///   desktop/web pickers honour.
/// - `uniformTypeIdentifiers` are REQUIRED by iOS: file_selector_ios throws an
///   `ArgumentError` for any type group that is not "allow all" yet carries no
///   UTIs. Without them (and with `openFile` called outside a try/catch) the
///   exception vanished silently and the "Choisir un fichier" button did
///   nothing at all on iPhone/iPad. `public.image` covers jpg/png/webp/heic.
const invoiceFileTypes = XTypeGroup(
  label: 'Factures',
  extensions: ['pdf', 'jpg', 'jpeg', 'png', 'webp'],
  mimeTypes: ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'],
  uniformTypeIdentifiers: ['com.adobe.pdf', 'public.image'],
);

class InvoicesScreen extends ConsumerStatefulWidget {
  const InvoicesScreen({super.key});

  @override
  ConsumerState<InvoicesScreen> createState() => _InvoicesScreenState();
}

class _InvoicesScreenState extends ConsumerState<InvoicesScreen> {
  bool _uploading = false;

  Future<void> _upload() async {
    final messenger = ScaffoldMessenger.of(context);

    // MUST stay inside try/catch: on iOS, openFile() throws an ArgumentError
    // synchronously if the type group has no uniformTypeIdentifiers. Left
    // uncaught (as it was), that exception silently aborted this callback and
    // the button looked completely dead — no picker, no error, nothing.
    final XFile? file;
    try {
      file = await openFile(acceptedTypeGroups: const [invoiceFileTypes]);
    } catch (e) {
      messenger.showSnackBar(const SnackBar(
        content: Text("Impossible d'ouvrir le sélecteur de fichiers."),
      ));
      return;
    }
    if (file == null) return;

    setState(() => _uploading = true);
    try {
      final bytes = await file.readAsBytes();
      if (bytes.isEmpty) {
        messenger.showSnackBar(const SnackBar(content: Text('Fichier illisible.')));
        return;
      }
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: file.name),
      });
      await ref.read(apiClientProvider).dio.post(
            '/invoices/ingest',
            data: form,
            options: Options(
              sendTimeout: const Duration(seconds: 120),
              receiveTimeout: const Duration(seconds: 120),
            ),
          );
      ref.invalidate(_invoicesProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Facture importée et analysée.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  ({String label, Color bg, Color fg}) _status(Map<String, dynamic> inv) {
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

  String _money(Map<String, dynamic> inv) {
    final total = inv['total_amount'] as num?;
    if (total == null) return '';
    final cur = inv['currency'];
    if (cur == null || cur == 'EUR' || cur == '€') return eur(total);
    return '${total.toStringAsFixed(2).replaceAll('.', ',')} $cur';
  }

  Widget _dropZone() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        border: Border.all(color: Theme.of(context).dividerColor, width: 2),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          const Text('📄', style: TextStyle(fontSize: 26)),
          const SizedBox(height: 4),
          const Text('Déposez une facture',
              style: TextStyle(fontFamily: 'Newsreader', fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 3),
          const Text("PDF ou photo — l'OCR extrait tout.",
              style: TextStyle(fontSize: 12, color: kMuted)),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: GradientButton(
              label: 'Choisir un fichier',
              onPressed: _uploading ? null : _upload,
              expand: true,
              loading: _uploading,
            ),
          ),
          const SizedBox(height: 4),
          TextButton.icon(
            onPressed: _uploading
                ? null
                : () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => const InvoiceSmartImportScreen(),
                    ));
                    ref.invalidate(_invoicesProvider);
                  },
            icon: const Icon(Icons.auto_awesome, size: 18, color: kTerracotta),
            label: const Text('Import intelligent — vérifier & valider'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: offlineCardList(
        ref: ref,
        provider: _invoicesProvider,
        header: _dropZone(),
        empty: 'Aucune facture pour le moment.',
        itemBuilder: (inv) {
          final st = _status(inv);
          return MockCard(
            onTap: () async {
              await Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => InvoiceDetailScreen(
                  invoiceId: '${inv['id']}',
                  invoiceNumber: inv['invoice_number'] as String?,
                ),
              ));
              ref.invalidate(_invoicesProvider);
            },
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text('${inv['invoice_number'] ?? 'Facture'}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                      decoration: BoxDecoration(color: st.bg, borderRadius: BorderRadius.circular(999)),
                      child: Text(st.label,
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: st.fg)),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: Text('${inv['date'] ?? ''}',
                          style: const TextStyle(fontSize: 12.5, color: kMuted)),
                    ),
                    Text(_money(inv),
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
