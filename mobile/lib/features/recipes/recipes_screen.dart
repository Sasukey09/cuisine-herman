import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kBorder, kCard, kGood, kBad;

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
    ]);
    if (data == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/recipes/', data: {
        'name': data['name'],
        'yield_qty': double.tryParse(data['yield_qty'] ?? '') ?? 1,
      });
      ref.invalidate(_recipesProvider);
      messenger.showSnackBar(
          const SnackBar(content: Text('Recette créée. Ajoutez ses ingrédients via l\'assistant.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
          return Container(
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              color: kCard,
              border: Border.all(color: kBorder),
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
                                        fontFamily: 'serif',
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
                        ],
                      ),
                    ),
                  ),
                ],
              ),
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
