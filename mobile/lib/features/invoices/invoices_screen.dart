import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: asyncListView(
        ref: ref,
        provider: _invoicesProvider,
        empty: 'Aucune facture. Touchez + pour importer une photo/PDF.',
        itemBuilder: (inv) {
          final total = inv['total_amount'];
          return ListTile(
            leading: const Icon(Icons.receipt_long_outlined),
            title: Text('${inv['invoice_number'] ?? 'Facture'}'),
            subtitle: Text('${inv['date'] ?? ''}'),
            trailing: Text(total != null ? '$total ${inv['currency'] ?? ''}' : ''),
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _uploading ? null : _upload,
        icon: _uploading
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.upload_file),
        label: Text(_uploading ? 'Analyse…' : 'Importer'),
      ),
    );
  }
}
