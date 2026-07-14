import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart' show kCard, kBorder, kMuted, kBad, kGood, kWarn;

final _dashProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/price-variations');
  return (resp.data as Map).cast<String, dynamic>();
});

final _alertsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/alerts/prices');
  return resp.data as List<dynamic>;
});

/// Les plats vendus en dessous de leur coût.
///
/// C'est le téléphone qu'on a en main dans la cuisine, et c'était précisément
/// l'écran qui ne le disait pas : l'accueil n'interrogeait que les alertes de
/// prix venues des factures, tout en intitulant sa tuile « prix & marges ».
final _lossProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/loss-making');
  return (resp.data as Map).cast<String, dynamic>();
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dash = ref.watch(_dashProvider);
    final alerts = ref.watch(_alertsProvider);
    final loss = ref.watch(_lossProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(_dashProvider);
        ref.invalidate(_alertsProvider);
        ref.invalidate(_lossProvider);
        await Future.wait([
          ref.read(_dashProvider.future),
          ref.read(_alertsProvider.future),
          ref.read(_lossProvider.future),
        ]);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
        children: [
          dash.when(
            loading: () => const _Loading(),
            error: (e, _) => ErrorState(onRetry: () => ref.invalidate(_dashProvider)),
            data: (d) {
              final up = (d['most_increased'] as List?) ?? const [];
              final down = (d['most_decreased'] as List?) ?? const [];
              final alertCount = alerts.maybeWhen(data: (a) => a.length, orElse: () => 0);
              final losing = loss.maybeWhen(
                  data: (l) => (l['losing_money'] as List?) ?? const [], orElse: () => const []);
              final lost = loss.maybeWhen(
                  data: (l) => (l['loss_per_portion_total'] as num?)?.toDouble() ?? 0.0,
                  orElse: () => 0.0);
              return GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 11,
                crossAxisSpacing: 11,
                childAspectRatio: 1.55,
                children: [
                  // En premier, et pas au milieu : « vous perdez de l'argent en ce
                  // moment » passe avant tout le reste.
                  _Stat(
                    label: 'Plats à perte',
                    value: '${losing.length}',
                    sub: losing.isEmpty ? 'aucun' : '${eur(lost)} / assiette',
                    subColor: losing.isEmpty ? kGood : kBad,
                  ),
                  // La sous-légende disait « prix & marges ». C'était faux : ce
                  // compteur ne voit que les alertes de prix venues des factures.
                  _Stat(label: 'Alertes de prix', value: '$alertCount', sub: 'sur les achats', subColor: kWarn),
                  _Stat(label: 'Produits en hausse', value: '${up.length}', sub: 'ce mois', subColor: kBad),
                  _Stat(label: 'Produits en baisse', value: '${down.length}', sub: 'ce mois', subColor: kGood),
                ],
              );
            },
          ),
          const SizedBox(height: 13),
          loss.when(
            loading: () => const SizedBox.shrink(),
            error: (e, _) => const SizedBox.shrink(),
            data: (l) {
              final losing = (l['losing_money'] as List?) ?? const [];
              final unknown = ((l['no_selling_price'] as List?) ?? const []).length +
                  ((l['not_costable'] as List?) ?? const []).length;
              return _SectionCard(
                icon: losing.isEmpty ? '\u2713' : '\u2198',
                iconColor: losing.isEmpty ? kGood : kBad,
                title: 'Plats vendus à perte',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (losing.isEmpty)
                      const _EmptyLine('Aucun plat vendu en dessous de son coût.')
                    else
                      for (final d in losing.take(5)) _lossRow(d as Map),
                    // Un plat qu'on ne peut pas évaluer n'est pas un plat sain :
                    // c'est exactement là que la perte se cache.
                    if (unknown > 0)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          unknown > 1
                              ? '$unknown plats non évaluables : prix de vente ou prix d’un ingrédient manquant.'
                              : '1 plat non évaluable : prix de vente ou prix d’un ingrédient manquant.',
                          style: const TextStyle(fontSize: 11.5, color: kMuted),
                        ),
                      ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(height: 13),
          dash.when(
            loading: () => const SizedBox.shrink(),
            error: (e, _) => const SizedBox.shrink(),
            data: (d) {
              final up = (d['most_increased'] as List?) ?? const [];
              return _SectionCard(
                icon: '▲',
                iconColor: kBad,
                title: 'Plus fortes hausses',
                child: up.isEmpty
                    ? const _EmptyLine('Aucune hausse détectée.')
                    : Column(children: [for (final r in up.take(4)) _moveRow(r as Map)]),
              );
            },
          ),
          const SizedBox(height: 13),
          alerts.when(
            loading: () => const _Loading(),
            error: (e, _) => ErrorState(onRetry: () => ref.invalidate(_alertsProvider)),
            data: (rows) => _SectionCard(
              icon: '⚠',
              iconColor: kWarn,
              title: 'Alertes de prix',
              child: rows.isEmpty
                  ? const _EmptyLine('Aucune alerte.')
                  : Column(
                      children: [
                        for (final r in rows.take(6))
                          Container(
                            margin: const EdgeInsets.only(bottom: 3),
                            padding: const EdgeInsets.fromLTRB(10, 5, 0, 5),
                            decoration: const BoxDecoration(
                              border: Border(left: BorderSide(color: Color(0xFFE0B07A), width: 2)),
                            ),
                            child: Text('${(r as Map)['message'] ?? ''}',
                                style: const TextStyle(fontSize: 12.5, color: Color(0xFF4A443C))),
                          ),
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _lossRow(Map d) {
    final loss = (d['loss_per_portion'] as num?)?.toDouble() ?? 0;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 7),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFECE4D4))),
      ),
      child: Row(children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${d['name'] ?? 'Recette'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text('coûte ${eur(d['cost_per_portion'] as num?)} · vendu ${eur(d['selling_price'] as num?)}',
                  style: const TextStyle(fontSize: 11.5, color: kMuted)),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: const Color(0xFFF6E1DC),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text('\u2212${eur(loss)} / assiette',
              style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: kBad)),
        ),
      ]),
    );
  }

  Widget _moveRow(Map m) {
    final pct = (m['change_pct'] as num?)?.toDouble() ?? 0;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 7),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFECE4D4))),
      ),
      child: Row(children: [
        Expanded(
          child: Text('${m['product_name'] ?? 'Produit'}',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(
            color: const Color(0xFFF6E1DC),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text('${pct > 0 ? '+' : ''}${pct.toStringAsFixed(1)} %',
              style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: kBad)),
        ),
      ]),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value, required this.sub, required this.subColor});
  final String label, value, sub;
  final Color subColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: kCard,
        border: Border.all(color: kBorder),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label, style: const TextStyle(fontSize: 11.5, color: kMuted, fontWeight: FontWeight.w500)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(fontFamily: 'serif', fontSize: 25, fontWeight: FontWeight.w600)),
          const SizedBox(height: 2),
          Text(sub, style: TextStyle(fontSize: 11, color: subColor, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.icon, required this.iconColor, required this.title, required this.child});
  final String icon, title;
  final Color iconColor;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: kCard,
        border: Border.all(color: kBorder),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(icon, style: TextStyle(color: iconColor, fontSize: 13)),
            const SizedBox(width: 7),
            Text(title, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) =>
      const Padding(padding: EdgeInsets.all(28), child: Center(child: CircularProgressIndicator()));
}


class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(text, style: const TextStyle(color: kMuted, fontSize: 12.5)));
}
