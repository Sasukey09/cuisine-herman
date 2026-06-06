import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../core/providers.dart';

final _recipesProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/recipes/', queryParameters: {'limit': 200});
  return resp.data as List<dynamic>;
});

class RecipesScreen extends ConsumerWidget {
  const RecipesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return asyncListView(
      ref: ref,
      provider: _recipesProvider,
      empty: 'Aucune recette. Créez-en via l\'assistant ou l\'import vidéo.',
      itemBuilder: (r) {
        final y = r['yield_qty'];
        return ListTile(
          leading: const Icon(Icons.menu_book_outlined),
          title: Text('${r['name'] ?? ''}'),
          subtitle: y != null ? Text('$y portion(s)') : null,
        );
      },
    );
  }
}
