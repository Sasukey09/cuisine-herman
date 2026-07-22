import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/edit_delete.dart';
import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kBad;
import '../auth/auth_controller.dart';
import 'recipe_detail_screen.dart';

final _recipesProvider = FutureProvider.autoDispose<Loaded>((ref) async {
  return fetchWithCache(ref, cacheKey: 'recipes', request: () async {
    final resp = await ref.read(apiClientProvider).dio.get('/recipes/enriched', queryParameters: {'limit': 200});
    return resp.data;
  });
});

const _emojis = ['🍽️', '🥗', '🍲', '🥘', '🍛', '🍚', '🥩', '🐟', '🍝', '🥧', '🍰', '🥦'];

class RecipesScreen extends ConsumerWidget {
  const RecipesScreen({super.key});

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final data = await showCreateDialog(context, title: 'Nouvelle recette', fields: const [
      CreateField('name', 'Nom', required: true),
      CreateField('yield_qty', 'Portions', keyboard: TextInputType.number),
      CreateField('selling_price', 'Prix de vente / portion (optionnel)',
          keyboard: TextInputType.number),
    ]);
    if (data == null) return;
    try {
      final sp = double.tryParse((data['selling_price'] ?? '').replaceAll(',', '.'));
      await ref.read(apiClientProvider).dio.post('/recipes/', data: {
        'name': data['name'],
        'yield_qty': double.tryParse(data['yield_qty'] ?? '') ?? 1,
        if (sp != null) 'selling_price': sp,
      });
      ref.invalidate(_recipesProvider);
      messenger.showSnackBar(
          const SnackBar(content: Text('Recette créée. Ajoutez ses ingrédients via l\'assistant.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _actions(BuildContext context, WidgetRef ref, Map<String, dynamic> r) async {
    final messenger = ScaffoldMessenger.of(context);
    final action = await showRowActions(context);
    if (action == null || !context.mounted) return;
    if (action == 'edit') {
      final data = await showEditDialog(
        context,
        title: 'Modifier la recette',
        fields: const [
          CreateField('name', 'Nom', required: true),
          CreateField('yield_qty', 'Portions', keyboard: TextInputType.number),
          CreateField('selling_price', 'Prix de vente (optionnel)', keyboard: TextInputType.number),
        ],
        initial: {
          'name': '${r['name'] ?? ''}',
          'yield_qty': r['yield_qty'] == null ? '' : '${r['yield_qty']}',
          'selling_price': r['selling_price'] == null ? '' : '${r['selling_price']}',
        },
      );
      if (data == null) return;
      await updateEntity(
        ref,
        messenger,
        path: '/recipes/${r['id']}',
        body: {
          'name': data['name'],
          if ((data['yield_qty'] ?? '').isNotEmpty) 'yield_qty': double.tryParse(data['yield_qty']!),
          if ((data['selling_price'] ?? '').isNotEmpty)
            'selling_price': double.tryParse(data['selling_price']!),
        },
        successMessage: 'Recette modifiée.',
        onDone: () => ref.invalidate(_recipesProvider),
      );
    } else {
      await confirmAndDelete(
        context,
        ref,
        messenger,
        path: '/recipes/${r['id']}',
        name: '${r['name'] ?? ''}',
        successMessage: 'Recette supprimée.',
        onDone: () => ref.invalidate(_recipesProvider),
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canWrite = ref.watch(canWriteProvider);
    return Scaffold(
      body: offlineCardList(
        ref: ref,
        header: const PendingWritesBanner(),
        provider: _recipesProvider,
        empty: 'Aucune recette. Touchez + (ou créez-en via l\'assistant / l\'import vidéo).',
        itemBuilder: (r) {
          final name = '${r['name'] ?? ''}';
          final emoji = _emojis[name.hashCode.abs() % _emojis.length];
          final margin = r['margin_pct'] as num?;
          final cost = r['cost_per_portion'] as num?;
          final price = r['selling_price'] as num?;
          final fc = (cost != null && price != null && price > 0)
              ? cost.toDouble() / price.toDouble() * 100
              : null;
          return GestureDetector(
            // Tap = ouvrir la recette (détail + ingrédients : ajouter/modifier/
            // supprimer, portions, coût recalculé), comme sur le Web. L'appui long
            // garde les actions rapides (modifier la fiche / supprimer).
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => RecipeDetailScreen(recipeId: '${r['id']}', recipeName: name),
            )),
            onLongPress: canWrite ? () => _actions(context, ref, r) : null,
            child: Container(
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              color: Theme.of(context).cardColor,
              border: Border.all(color: Theme.of(context).dividerColor),
              borderRadius: BorderRadius.circular(14),
            ),
            // IntrinsicHeight n'est pas décoratif : sans lui, cet écran est BLANC.
            //
            // Une ListView donne à ses enfants une hauteur non bornée, et
            // `CrossAxisAlignment.stretch` demande justement aux enfants de la
            // remplir — donc l'infini. Flutter lève une erreur de mise en page, et
            // en release une erreur de mise en page ne s'affiche pas : elle ne
            // rend RIEN. Pas de message, pas d'écran rouge. Juste des recettes
            // invisibles, alors que l'API les renvoyait toutes.
            //
            // IntrinsicHeight borne la hauteur sur celle du plus grand enfant (la
            // tuile emoji, 74), ce qui rend `stretch` calculable et garde
            // l'intention d'origine : le carré de couleur monte jusqu'aux bords
            // de la carte.
            child: IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Container(
                    width: 74,
                    height: 74,
                    alignment: Alignment.center,
                    color: const Color(0xFFEFE1D3),
                    child: Text(emoji, style: const TextStyle(fontSize: 30)),
                  ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(14, 11, 14, 11),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(name,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                        fontFamily: 'Newsreader',
                                        fontSize: 15.5,
                                        fontWeight: FontWeight.w600)),
                              ),
                              const SizedBox(width: 8),
                              // Une marge négative n'est pas une bonne nouvelle : la
                              // peindre en vert comme les autres serait un mensonge.
                              Text(margin == null ? '—' : pctRound(margin),
                                  style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: (margin != null && margin < 0) ? kBad : kGood)),
                            ],
                          ),
                          const SizedBox(height: 3),
                          Text('${eur(cost)}/portion · vente ${eur(price)}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 12, color: kMuted)),
                          if (fc != null) ...[
                            const SizedBox(height: 7),
                            Row(
                              children: [
                                Expanded(child: FoodCostBar(percent: fc)),
                                const SizedBox(width: 8),
                                Text('${fc.round()} %',
                                    style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: fc >= 33 ? kBad : kMuted)),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ));
        },
      ),
      floatingActionButton:
          canWrite ? GradientFab(onPressed: () => _create(context, ref)) : null,
    );
  }
}
