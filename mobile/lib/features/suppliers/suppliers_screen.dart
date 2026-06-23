import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kTerracotta, kWarn;

final _suppliersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/enriched');
  return resp.data as List<dynamic>;
});

class SuppliersScreen extends ConsumerWidget {
  const SuppliersScreen({super.key});

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final data = await showCreateDialog(context, title: 'Nouveau fournisseur', fields: const [
      CreateField('name', 'Nom', required: true),
      CreateField('code', 'Code (optionnel)'),
    ]);
    if (data == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/suppliers/', data: {
        'name': data['name'],
        if ((data['code'] ?? '').isNotEmpty) 'code': data['code'],
      });
      ref.invalidate(_suppliersProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Fournisseur créé.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: asyncCardList(
        ref: ref,
        provider: _suppliersProvider,
        empty: 'Aucun fournisseur. Touchez + pour en ajouter.',
        itemBuilder: (s) {
          final name = '${s['name'] ?? ''}';
          final initial = name.isNotEmpty ? name[0].toUpperCase() : '?';
          final count = s['product_count'] ?? 0;
          final type = (s['code'] ?? '').toString().isNotEmpty ? '${s['code']}' : 'Fournisseur';
          final rating = s['rating'] as num?;
          return MockCard(
            child: Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: const Color(0xFFEFE1D3),
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: Text(initial,
                      style: const TextStyle(
                          fontFamily: 'serif', fontSize: 18, fontWeight: FontWeight.w600, color: kTerracotta)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 2),
                      Text('$type · $count produit${count == 1 ? '' : 's'}',
                          style: const TextStyle(fontSize: 12, color: kMuted)),
                    ],
                  ),
                ),
                if (rating != null)
                  Text('★ ${rating.toString().replaceAll('.', ',')}',
                      style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: kWarn)),
              ],
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _create(context, ref),
        child: const Icon(Icons.add),
      ),
    );
  }
}
