import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';

final _recipesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/recipes/', queryParameters: {'limit': 200});
  return resp.data as List<dynamic>;
});

class RecipesScreen extends ConsumerWidget {
  const RecipesScreen({super.key});

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final data = await showCreateDialog(context, title: 'Nouvelle recette', fields: const [
      CreateField('name', 'Nom', required: true),
      CreateField('yield_qty', 'Portions', keyboard: TextInputType.number),
    ]);
    if (data == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/recipes/', data: {
        'name': data['name'],
        'yield_qty': double.tryParse(data['yield_qty'] ?? '') ?? 1,
      });
      ref.invalidate(_recipesProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Recette créée. Ajoutez ses ingrédients via l\'assistant.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: asyncListView(
        ref: ref,
        provider: _recipesProvider,
        empty: 'Aucune recette. Touchez + (ou créez-en via l\'assistant / l\'import vidéo).',
        itemBuilder: (r) {
          final y = r['yield_qty'];
          return ListTile(
            leading: const Icon(Icons.menu_book_outlined),
            title: Text('${r['name'] ?? ''}'),
            subtitle: y != null ? Text('$y portion(s)') : null,
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
