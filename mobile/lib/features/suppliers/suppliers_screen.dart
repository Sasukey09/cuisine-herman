import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/edit_delete.dart';
import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kTerracotta, kWarn;
import '../auth/auth_controller.dart';
import 'supplier_detail_screen.dart';

final suppliersSearchQueryProvider = StateProvider.autoDispose<String>((ref) => '');

final _suppliersProvider = FutureProvider.autoDispose<Loaded>((ref) async {
  // Read the query BEFORE the await so Riverpod registers the dependency (the
  // exact bug that once broke the products search — see products_screen).
  final q = ref.watch(suppliersSearchQueryProvider).trim();
  return fetchWithCache(ref, cacheKey: 'suppliers${q.isEmpty ? '' : ':$q'}', request: () async {
    final resp = await ref.read(apiClientProvider).dio.get('/suppliers/enriched',
        queryParameters: q.isEmpty ? null : {'q': q});
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
      CreateField('email', 'Email (optionnel)', keyboard: TextInputType.emailAddress),
      CreateField('phone', 'Téléphone (optionnel)', keyboard: TextInputType.phone),
      CreateField('rating', 'Note /5 (optionnel)', keyboard: TextInputType.number),
    ]);
    if (data == null) return;
    await createOrQueue(
      ref,
      messenger,
      path: '/suppliers/',
      body: {
        'name': data['name'],
        if ((data['code'] ?? '').isNotEmpty) 'code': data['code'],
        ..._contactAndRating(data),
      },
      label: 'Fournisseur : ${data['name']}',
      successMessage: 'Fournisseur créé.',
      onDone: () => ref.invalidate(_suppliersProvider),
    );
  }

  /// Build the `contact` dict (email/phone) + `rating` from form fields, exactly
  /// like the web supplier form. Empty fields are omitted.
  Map<String, dynamic> _contactAndRating(Map<String, dynamic> data) {
    final contact = <String, dynamic>{
      if ((data['email'] ?? '').toString().isNotEmpty) 'email': data['email'],
      if ((data['phone'] ?? '').toString().isNotEmpty) 'phone': data['phone'],
    };
    final rating = double.tryParse((data['rating'] ?? '').toString().replaceAll(',', '.'));
    return {
      if (contact.isNotEmpty) 'contact': contact,
      if (rating != null) 'rating': rating,
    };
  }

  Future<void> _actions(BuildContext context, WidgetRef ref, Map<String, dynamic> s) async {
    final messenger = ScaffoldMessenger.of(context);
    final action = await showRowActions(context);
    if (action == null || !context.mounted) return;
    if (action == 'edit') {
      final contact = (s['contact'] as Map?) ?? const {};
      final data = await showEditDialog(
        context,
        title: 'Modifier le fournisseur',
        fields: const [
          CreateField('name', 'Nom', required: true),
          CreateField('code', 'Code (optionnel)'),
          CreateField('email', 'Email (optionnel)', keyboard: TextInputType.emailAddress),
          CreateField('phone', 'Téléphone (optionnel)', keyboard: TextInputType.phone),
          CreateField('rating', 'Note /5 (optionnel)', keyboard: TextInputType.number),
        ],
        initial: {
          'name': '${s['name'] ?? ''}',
          'code': '${s['code'] ?? ''}',
          'email': '${contact['email'] ?? ''}',
          'phone': '${contact['phone'] ?? ''}',
          'rating': s['rating'] == null ? '' : '${s['rating']}',
        },
      );
      if (data == null) return;
      await updateEntity(
        ref,
        messenger,
        path: '/suppliers/${s['id']}',
        body: {
          'name': data['name'],
          'code': (data['code'] ?? '').isEmpty ? null : data['code'],
          ..._contactAndRating(data),
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
    final canWrite = ref.watch(canWriteProvider);
    return Scaffold(
      body: offlineCardList(
        ref: ref,
        header: Column(children: [
          const PendingWritesBanner(),
          _SupplierSearch(
              onChanged: (v) =>
                  ref.read(suppliersSearchQueryProvider.notifier).state = v),
        ]),
        provider: _suppliersProvider,
        empty: 'Aucun fournisseur. Touchez + pour en ajouter.',
        itemBuilder: (s) {
          final name = '${s['name'] ?? ''}';
          final initial = name.isNotEmpty ? name[0].toUpperCase() : '?';
          final count = s['product_count'] ?? 0;
          final type = (s['code'] ?? '').toString().isNotEmpty ? '${s['code']}' : 'Fournisseur';
          final rating = s['rating'] as num?;
          return GestureDetector(
            // Tap = fiche détail (coordonnées + historique + catalogue prix),
            // comme « Voir le catalogue » du web. Appui long = actions.
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
              builder: (_) =>
                  SupplierDetailScreen(supplierId: '${s['id']}', supplierName: name),
            )),
            onLongPress: canWrite ? () => _actions(context, ref, s) : null,
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
      floatingActionButton:
          canWrite ? GradientFab(onPressed: () => _create(context, ref)) : null,
    );
  }
}

/// Debounced supplier search field (mirrors the products search). Forwards the
/// query to `suppliersSearchQueryProvider`, which the enriched list watches.
class _SupplierSearch extends StatefulWidget {
  const _SupplierSearch({required this.onChanged});
  final ValueChanged<String> onChanged;

  @override
  State<_SupplierSearch> createState() => _SupplierSearchState();
}

class _SupplierSearchState extends State<_SupplierSearch> {
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _onChanged(String value) {
    _timer?.cancel();
    _timer = Timer(const Duration(milliseconds: 350), () => widget.onChanged(value));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      decoration: BoxDecoration(
        color: theme.cardColor,
        border: Border.all(color: theme.dividerColor),
        borderRadius: BorderRadius.circular(11),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Row(
        children: [
          const Icon(Icons.search, size: 16, color: kMuted),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              onChanged: _onChanged,
              style: const TextStyle(fontSize: 13),
              decoration: const InputDecoration(
                isCollapsed: true,
                filled: false,
                border: InputBorder.none,
                hintText: 'Rechercher un fournisseur…',
                contentPadding: EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
