import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/edit_delete.dart';
import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kTerracotta, kWarn;

final _suppliersProvider = FutureProvider.autoDispose<Loaded>((ref) async {
  return fetchWithCache(ref, cacheKey: 'suppliers', request: () async {
    final resp = await ref.read(apiClientProvider).dio.get('/suppliers/enriched');
    return resp.data;
  });
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
    await createOrQueue(
      ref,
      messenger,
      path: '/suppliers/',
      body: {
        'name': data['name'],
        if ((data['code'] ?? '').isNotEmpty) 'code': data['code'],
      },
      label: 'Fournisseur : ${data['name']}',
      successMessage: 'Fournisseur créé.',
      onDone: () => ref.invalidate(_suppliersProvider),
    );
  }

  Future<void> _actions(BuildContext context, WidgetRef ref, Map<String, dynamic> s) async {
    final messenger = ScaffoldMessenger.of(context);
    final action = await showRowActions(context);
    if (action == null || !context.mounted) return;
    if (action == 'edit') {
      final data = await showEditDialog(
        context,
        title: 'Modifier le fournisseur',
        fields: const [
          CreateField('name', 'Nom', required: true),
          CreateField('code', 'Code (optionnel)'),
        ],
        initial: {'name': '${s['name'] ?? ''}', 'code': '${s['code'] ?? ''}'},
      );
      if (data == null) return;
      await updateEntity(
        ref,
        messenger,
        path: '/suppliers/${s['id']}',
        body: {
          'name': data['name'],
          'code': (data['code'] ?? '').isEmpty ? null : data['code'],
        },
        successMessage: 'Fournisseur modifié.',
        onDone: () => ref.invalidate(_suppliersProvider),
      );
    } else {
      await confirmAndDelete(
        context,
        ref,
        messenger,
        path: '/suppliers/${s['id']}',
        name: '${s['name'] ?? ''}',
        successMessage: 'Fournisseur supprimé.',
        onDone: () => ref.invalidate(_suppliersProvider),
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: offlineCardList(
        ref: ref,
        header: const PendingWritesBanner(),
        provider: _suppliersProvider,
        empty: 'Aucun fournisseur. Touchez + pour en ajouter.',
        itemBuilder: (s) {
          final name = '${s['name'] ?? ''}';
          final initial = name.isNotEmpty ? name[0].toUpperCase() : '?';
          final count = s['product_count'] ?? 0;
          final type = (s['code'] ?? '').toString().isNotEmpty ? '${s['code']}' : 'Fournisseur';
          final rating = s['rating'] as num?;
          return GestureDetector(
            // Un tap ouvre les actions (modifier / supprimer) : sans onTap, la
            // carte ne reagissait qu'a l'appui long, non decouvrable -> l'usager
            // avait l'impression de "ne pas pouvoir cliquer".
            onTap: () => _actions(context, ref, s),
            onLongPress: () => _actions(context, ref, s),
            child: MockCard(
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
                          fontFamily: 'Newsreader', fontSize: 18, fontWeight: FontWeight.w600, color: kTerracotta)),
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
          ));
        },
      ),
      floatingActionButton: GradientFab(onPressed: () => _create(context, ref)),
    );
  }
}
