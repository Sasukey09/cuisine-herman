import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart'
    show kMuted, kBad, kGood, kWarn, kSerif, kGradTeal, kGradAmber, kGradDanger, kGradTerracotta;

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

/// Historique des coûts calculés (un point par version de recette costée).
/// Alimente les tuiles de synthèse (coût moyen, food cost) et le mini-graphe.
final _costTrendsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/cost-trends');
  return resp.data as List<dynamic>;
});

/// Produits classés par dépense cumulée (factures).
final _topProductsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/top-products', queryParameters: {'limit': 100});
  return resp.data as List<dynamic>;
});

/// Recettes dont le food cost dépasse le seuil (35 % par défaut côté backend).
final _marginAlertsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/margin-alerts');
  return resp.data as List<dynamic>;
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dash = ref.watch(_dashProvider);
    final alerts = ref.watch(_alertsProvider);
    final loss = ref.watch(_lossProvider);
    final costTrends = ref.watch(_costTrendsProvider);
    final topProducts = ref.watch(_topProductsProvider);
    final marginAlerts = ref.watch(_marginAlertsProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(_dashProvider);
        ref.invalidate(_alertsProvider);
        ref.invalidate(_lossProvider);
        ref.invalidate(_costTrendsProvider);
        ref.invalidate(_topProductsProvider);
        ref.invalidate(_marginAlertsProvider);
        await Future.wait([
          ref.read(_dashProvider.future),
          ref.read(_alertsProvider.future),
          ref.read(_lossProvider.future),
          ref.read(_costTrendsProvider.future),
          ref.read(_topProductsProvider.future),
          ref.read(_marginAlertsProvider.future),
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
                    gradient: losing.isEmpty ? kGradTeal : kGradDanger,
                  ),
                  // La sous-légende disait « prix & marges ». C'était faux : ce
                  // compteur ne voit que les alertes de prix venues des factures.
                  _Stat(
                    label: 'Alertes de prix',
                    value: '$alertCount',
                    sub: 'sur les achats',
                    gradient: alertCount > 0 ? kGradAmber : kGradTeal,
                  ),
                  _Stat(label: 'Produits en hausse', value: '${up.length}', sub: 'ce mois', subColor: kBad),
                  _Stat(label: 'Produits en baisse', value: '${down.length}', sub: 'ce mois', subColor: kGood),
                ],
              );
            },
          ),
          const SizedBox(height: 13),
          // — Synthèse coût/marge (parité web) : coût matière moyen / portion,
          //   food cost moyen (dérivés du dernier point costé par recette) et
          //   dépense cumulée (somme des top-produits). —
          costTrends.when(
            loading: () => const _Loading(),
            error: (e, _) => ErrorState(onRetry: () => ref.invalidate(_costTrendsProvider)),
            data: (points) {
              final latest = _latestPerVersion(points);
              final avgCost = _avg(latest.map((p) => p['cost_per_portion'] as num?));
              final avgFc = _avg(latest.map((p) => p['food_cost_pct'] as num?));
              final totalSpend = topProducts.maybeWhen(
                data: (ps) => ps.fold<double>(
                    0, (s, p) => s + (((p as Map)['total_spend'] as num?)?.toDouble() ?? 0)),
                orElse: () => null,
              );
              return GridView.count(
                crossAxisCount: 3,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                childAspectRatio: 1.0,
                children: [
                  _MiniStat(
                      label: 'Coût matière / portion',
                      value: eur(avgCost),
                      gradient: kGradTerracotta),
                  _MiniStat(
                      label: 'Food cost moyen',
                      value: pctRound(avgFc),
                      gradient: kGradAmber),
                  _MiniStat(
                      label: 'Dépense cumulée',
                      value: totalSpend == null ? '…' : eur(totalSpend),
                      gradient: kGradTeal),
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
          // — Évolution des coûts : mini bar-chart maison (aucune lib de graphe). —
          costTrends.when(
            loading: () => const SizedBox.shrink(),
            error: (e, _) => const SizedBox.shrink(),
            data: (points) => _SectionCard(
              icon: '↗',
              iconColor: kMuted,
              title: 'Évolution du coût matière',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Coût moyen / portion dans le temps',
                      style: TextStyle(fontSize: 11.5, color: kMuted)),
                  const SizedBox(height: 10),
                  _CostTrendMiniChart(_aggregateByDay(points)),
                ],
              ),
            ),
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
          // — Alertes de marge : recettes au food cost élevé (seuil backend). —
          marginAlerts.when(
            loading: () => const _Loading(),
            error: (e, _) => ErrorState(onRetry: () => ref.invalidate(_marginAlertsProvider)),
            data: (rows) => _SectionCard(
              icon: rows.isEmpty ? '✓' : '⚠',
              iconColor: rows.isEmpty ? kGood : kWarn,
              title: 'Alertes de marge',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Recettes au food cost supérieur à 35 %',
                      style: TextStyle(fontSize: 11.5, color: kMuted)),
                  const SizedBox(height: 6),
                  if (rows.isEmpty)
                    const _EmptyLine('Aucune recette en alerte.')
                  else
                    for (final a in rows.take(6)) _marginRow(a as Map),
                ],
              ),
            ),
          ),
          const SizedBox(height: 13),
          // — Top produits par dépense cumulée (barres proportionnelles). —
          topProducts.when(
            loading: () => const _Loading(),
            error: (e, _) => ErrorState(onRetry: () => ref.invalidate(_topProductsProvider)),
            data: (rows) {
              final top = rows.take(8).toList();
              var maxSpend = 0.0;
              for (final p in top) {
                final s = ((p as Map)['total_spend'] as num?)?.toDouble() ?? 0;
                if (s > maxSpend) maxSpend = s;
              }
              return _SectionCard(
                icon: '■',
                iconColor: kGood,
                title: 'Top produits (dépense)',
                child: top.isEmpty
                    ? const _EmptyLine('Aucun achat enregistré.')
                    : Column(children: [for (final p in top) _topProductRow(p as Map, maxSpend)]),
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
                                style: TextStyle(
                                    fontSize: 12.5,
                                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: .85))),
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

  /// Une recette en alerte de marge : nom, coût/portion et badge food cost.
  /// Rouge au-delà de 45 % (comme le badge « destructive » du web), ambre sinon.
  Widget _marginRow(Map a) {
    final fc = (a['food_cost_pct'] as num?)?.toDouble();
    final hot = (fc ?? 0) > 45;
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
              Text('${a['recipe_name'] ?? 'Recette'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text('coût/portion ${eur(a['cost_per_portion'] as num?)}',
                  style: const TextStyle(fontSize: 11.5, color: kMuted)),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: hot ? const Color(0xFFF6E1DC) : const Color(0xFFF6EAD4),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(pctRound(fc),
              style: TextStyle(
                  fontSize: 11.5, fontWeight: FontWeight.w600, color: hot ? kBad : kWarn)),
        ),
      ]),
    );
  }

  /// Une ligne « top produit » : nom, dépense cumulée et une barre proportionnelle
  /// (largeur = dépense / dépense max), sans librairie de graphe.
  Widget _topProductRow(Map p, double max) {
    final spend = (p['total_spend'] as num?)?.toDouble() ?? 0;
    final frac = max <= 0 ? 0.0 : (spend / max);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Text('${p['name'] ?? '—'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            ),
            const SizedBox(width: 8),
            Text(eur(spend),
                style: const TextStyle(fontSize: 12, color: kMuted, fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 5),
          Container(
            height: 6,
            decoration: BoxDecoration(
              color: const Color(0xFFECE4D4),
              borderRadius: BorderRadius.circular(999),
            ),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: frac.clamp(0.04, 1.0).toDouble(),
              child: Container(
                decoration: BoxDecoration(
                  gradient: kGradTeal,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Tuile de statistique. Deux traitements fidèles au design :
///  • dégradé (métriques « argent à risque ») — grand chiffre serif blanc, la
///    couleur du dégradé porte le signal (teal calme / rouge / ambre) ;
///  • carte crème (métriques de mouvement) — chiffre serif encre + sous-légende
///    à couleur sémantique (vert/rouge).
class _Stat extends StatelessWidget {
  const _Stat({
    required this.label,
    required this.value,
    required this.sub,
    this.subColor,
    this.gradient,
  });
  final String label, value, sub;
  final Color? subColor;
  final Gradient? gradient;

  @override
  Widget build(BuildContext context) {
    final onGrad = gradient != null;
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: gradient,
        color: onGrad ? null : theme.cardColor,
        border: onGrad ? null : Border.all(color: theme.dividerColor),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11.5,
              color: onGrad ? Colors.white.withValues(alpha: .85) : kMuted,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: kSerif.copyWith(
              fontSize: 25,
              fontWeight: FontWeight.w700,
              color: onGrad ? Colors.white : theme.colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            sub,
            style: TextStyle(
              fontSize: 11,
              color: onGrad ? Colors.white.withValues(alpha: .9) : (subColor ?? kMuted),
              fontWeight: FontWeight.w600,
            ),
          ),
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
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: theme.cardColor,
        border: Border.all(color: theme.dividerColor),
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

// ── Dérivations des cost-trends (parité web features/dashboard/utils.ts) ──

/// Ne garde que le point costé le plus récent par version de recette.
List<Map> _latestPerVersion(List<dynamic> points) {
  final byVersion = <String, Map>{};
  for (final raw in points) {
    final p = raw as Map;
    final vid = '${p['recipe_version_id'] ?? ''}';
    final prev = byVersion[vid];
    final at = p['computed_at'] as String?;
    final prevAt = prev?['computed_at'] as String?;
    if (prev == null || (at != null && prevAt != null && at.compareTo(prevAt) > 0)) {
      byVersion[vid] = p;
    }
  }
  return byVersion.values.toList();
}

/// Moyenne des valeurs non nulles ; null si la liste est vide.
double? _avg(Iterable<num?> values) {
  var sum = 0.0;
  var n = 0;
  for (final v in values) {
    if (v == null) continue;
    sum += v;
    n++;
  }
  return n == 0 ? null : sum / n;
}

/// Coût moyen / portion agrégé par jour (parité web aggregateByDay), trié.
List<_DailyCost> _aggregateByDay(List<dynamic> points) {
  final groups = <String, List<double>>{};
  for (final raw in points) {
    final p = raw as Map;
    final at = p['computed_at'] as String?;
    if (at == null || at.length < 10) continue;
    final cost = (p['cost_per_portion'] as num?)?.toDouble();
    if (cost == null) continue;
    (groups[at.substring(0, 10)] ??= <double>[]).add(cost);
  }
  final days = groups.keys.toList()..sort();
  return [
    for (final d in days)
      _DailyCost(d, groups[d]!.reduce((a, b) => a + b) / groups[d]!.length),
  ];
}

/// "2026-07-21" -> "21/07".
String _shortDate(String iso) =>
    iso.length < 10 ? iso : '${iso.substring(8, 10)}/${iso.substring(5, 7)}';

class _DailyCost {
  const _DailyCost(this.date, this.avgCost);
  final String date;
  final double avgCost;
}

/// Tuile de synthèse compacte (3 par ligne). Grand chiffre serif blanc sur
/// dégradé ; [FittedBox] pour ne jamais déborder sur les gros montants.
class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.label, required this.value, required this.gradient});
  final String label, value;
  final Gradient gradient;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(gradient: gradient, borderRadius: BorderRadius.circular(14)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value,
                style: kSerif.copyWith(
                    fontSize: 21, fontWeight: FontWeight.w700, color: Colors.white)),
          ),
          const SizedBox(height: 4),
          Text(label,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: 10.5,
                  height: 1.15,
                  color: Colors.white.withValues(alpha: .9),
                  fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

/// Mini bar-chart maison : une barre par jour, hauteur proportionnelle au coût
/// moyen / portion. Aucune librairie de graphe (interdit).
class _CostTrendMiniChart extends StatelessWidget {
  const _CostTrendMiniChart(this.daily);
  final List<_DailyCost> daily;

  @override
  Widget build(BuildContext context) {
    if (daily.isEmpty) {
      return const _EmptyLine(
          'Pas encore de données de coût. Calculez le coût d’une recette.');
    }
    // On limite aux 14 derniers jours pour rester lisible sur un téléphone.
    final pts = daily.length > 14 ? daily.sublist(daily.length - 14) : daily;
    var maxV = 0.0;
    for (final d in pts) {
      if (d.avgCost > maxV) maxV = d.avgCost;
    }
    final safeMax = maxV <= 0 ? 1.0 : maxV;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 92,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              for (final d in pts)
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    child: Container(
                      height: (d.avgCost / safeMax) * 80 + 3,
                      decoration: BoxDecoration(
                        gradient: kGradTeal,
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 6),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(_shortDate(pts.first.date),
                style: const TextStyle(fontSize: 10.5, color: kMuted)),
            Text('max ${eur(maxV)}',
                style: const TextStyle(fontSize: 10.5, color: kMuted, fontWeight: FontWeight.w600)),
            Text(_shortDate(pts.last.date),
                style: const TextStyle(fontSize: 10.5, color: kMuted)),
          ],
        ),
      ],
    );
  }
}
