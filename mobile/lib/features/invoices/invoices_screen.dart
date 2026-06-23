import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kInk, kGood, kWarn;

final _invoicesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/invoices/');
  return resp.data as List<dynamic>;
});

class InvoicesScreen extends ConsumerStatefulWidget {
  const InvoicesScreen({super.key});

  @override
  ConsumerState<InvoicesScreen> createState() => _InvoicesScreenState();
}

class _InvoicesScreenState extends ConsumerState<InvoicesScreen> {
  bool _uploading = false;

  Future<void> _upload() async {
    final messenger = ScaffoldMessenger.of(context);
    final picked = await FilePicker.platform.pickFiles(
      withData: true,
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'jpg', 'jpeg', 'png', 'webp'],
    );
    if (picked == null || picked.files.isEmpty) return;
    final file = picked.files.first;
    if (file.bytes == null) {
      messenger.showSnackBar(const SnackBar(content: Text('Fichier illisible.')));
      return;
    }

    setState(() => _uploading = true);
    try {
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(file.bytes!, filename: file.name),
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
        color: const Color(0xFFFAF6EE),
        border: Border.all(color: const Color(0xFFD6C9B4), width: 2),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          const Text('📄', style: TextStyle(fontSize: 26)),
          const SizedBox(height: 4),
          const Text('Déposez une facture',
              style: TextStyle(fontFamily: 'serif', fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 3),
          const Text("PDF ou photo — l'OCR extrait tout.",
              style: TextStyle(fontSize: 12, color: kMuted)),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _uploading ? null : _upload,
              child: _uploading
                  ? const SizedBox(
                      height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Text('Choisir un fichier'),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: asyncCardList(
        ref: ref,
        provider: _invoicesProvider,
        header: _dropZone(),
        empty: 'Aucune facture pour le moment.',
        itemBuilder: (inv) {
          final st = _status(inv);
          return MockCard(
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
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kInk)),
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
