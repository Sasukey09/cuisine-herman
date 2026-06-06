import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../core/providers.dart';

final _invoicesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/invoices/');
  return resp.data as List<dynamic>;
});

class InvoicesScreen extends ConsumerWidget {
  const InvoicesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return asyncListView(
      ref: ref,
      provider: _invoicesProvider,
      empty: 'Aucune facture. L\'import OCR se fait depuis le web.',
      itemBuilder: (inv) {
        final total = inv['total_amount'];
        return ListTile(
          leading: const Icon(Icons.receipt_long_outlined),
          title: Text('${inv['invoice_number'] ?? 'Facture'}'),
          subtitle: Text('${inv['date'] ?? ''}'),
          trailing: Text(total != null ? '$total ${inv['currency'] ?? ''}' : ''),
        );
      },
    );
  }
}
