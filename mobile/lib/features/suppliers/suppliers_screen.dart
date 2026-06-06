import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../core/providers.dart';

final _suppliersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/');
  return resp.data as List<dynamic>;
});

class SuppliersScreen extends ConsumerWidget {
  const SuppliersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return asyncListView(
      ref: ref,
      provider: _suppliersProvider,
      empty: 'Aucun fournisseur.',
      itemBuilder: (s) => ListTile(
        leading: const Icon(Icons.local_shipping_outlined),
        title: Text('${s['name'] ?? ''}'),
        subtitle: s['code'] != null ? Text('Code ${s['code']}') : null,
      ),
    );
  }
}
