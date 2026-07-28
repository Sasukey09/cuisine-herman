import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart'
    show kMuted, kBad, kGood, kWarn, kTerracotta, kSerif, kGradTeal, kGradAmber, kGradDanger, kGradBrand;
import '../common/kpi_widgets.dart';
import '../prix/price_screen.dart';

/// Pilotage Achats — l'équivalent mobile de la page web `/pilotage`
/// (`frontend/src/features/pilotage/pilotage-view.tsx`) : une seule requête
/// `GET /purchasing/kpi` qui synthétise tout le cycle achats (économies,
/// commandé/reçu/facturé, prix, fournisseurs), rendue avec les widgets KPI
/// partagés avec l'accueil (`features/common/kpi_widgets.dart`).
final _kpiProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/purchasing/kpi');
  return (resp.data as Map).cast<String, dynamic>();
});

class PilotageScreen extends ConsumerWidget {
  const PilotageScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final kpi = ref.watch(_kpiProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(_kpiProvider);
        await ref.read(_kpiProvider.future);
      },
      child: kpi.when(
        loading: () => ListView(
          children: const [
            Padding(
              padding: EdgeInsets.all(28),
              child: Center(child: CircularProgressIndicator()),
            ),
          ],
        ),
        error: (e, _) => ListView(
          children: [ErrorState(onRetry: () => ref.invalidate(_kpiProvider))],
        ),
        data: (d) => _PilotageBody(d),
      ),
    );
  }
}

/// Corps de l'écran une fois `/purchasing/kpi` chargé. Sorti de [PilotageScreen]
/// pour ne pas reconstruire les helpers de formatage à chaque frame.
class _PilotageBody extends StatelessWidget {
  const _PilotageBody(this.data);
  final Map<String, dynamic> data;

  Map<String, dynamic> _map(dynamic v) => Map<String, dynamic>.from((v as Map?) ?? const {});
  List<dynamic> _list(dynamic v) => (v as List?) ?? const [];

  /// Libellé servi par le backend (source unique web + mobile), avec repli
  /// FR si la clé manque — cf. `KPI_LABELS` / `SAVINGS_LABELS`
  /// (`backend/app/services/purchasing/kpi_service.py` et `savings_service.py`).
  String _label(Map<String, dynamic> labels, String key, String fallback) =>
      (labels[key] as String?) ?? fallback;

  @override
  Widget build(BuildContext context) {
    final savings = _map(data['savings']);
    final savingsLabels = _map(savings['labels']);
    final cycle = _map(data['cycle']);
    final price = _map(data['price']);
    final suppliers = _map(data['suppliers']);
    final topProducts = _list(data['top_products']);
    final labels = _map(data['labels']);
    final rate = savings['best_choice_rate'] as num?;
    final comparedLines = plainNumber((savings['compared_lines'] as num?) ?? 0);

    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
      children: [
        // Pas de titre/paragraphe ici : le shell (`HomeShell`) affiche déjà
        // « Pilotage / Vue d'ensemble des achats » au-dessus de l'écran — même
        // convention que `PriceScreen`/`VideoImportScreen`, qui n'ont pas non
        // plus de titre interne. Le seul signal propre à cet écran (la fenêtre
        // glissante) est replié dans la légende de la section Économies.
        _Section('Économies', caption: '${data['window_months']} mois'),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 11,
          crossAxisSpacing: 11,
          childAspectRatio: 1.55,
          children: [
            KpiStat(
              label: _label(savingsLabels, 'realized', 'Économisé'),
              value: eur(savings['realized'] as num?),
              sub: '$comparedLines ligne(s) comparée(s)',
              gradient: kGradTeal,
            ),
            KpiStat(
              label: _label(savingsLabels, 'missed', 'Laissé sur la table'),
              value: eur(savings['missed'] as num?),
              sub: '${data['window_months']} mois glissants',
              gradient: kGradDanger,
            ),
            KpiStat(
              label: _label(savingsLabels, 'best_choice_rate', 'Taux de meilleur choix'),
              value: rate == null ? '—' : '${(rate * 100).round()} %',
              sub: 'lignes au meilleur prix',
              gradient: kGradAmber,
            ),
            KpiStat(
              label: _label(labels, 'possible_open', 'Économies possibles (devis ouverts)'),
              value: eur(data['possible_open'] as num?),
              sub: 'devis en cours',
              gradient: kGradBrand,
            ),
          ],
        ),

        const SizedBox(height: 18),
        const _Section('Cycle achats'),
        GridView.count(
          crossAxisCount: 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 1.0,
          children: [
            KpiMiniStat(
              label: _label(labels, 'ordered_total', 'Commandé'),
              value: eur(cycle['ordered_total'] as num?),
              gradient: kGradTeal,
            ),
            KpiMiniStat(
              label: _label(labels, 'received_value', 'Reçu'),
              value: eur(cycle['received_value'] as num?),
              gradient: kGradAmber,
            ),
            KpiMiniStat(
              label: _label(labels, 'billed_total', 'Facturé'),
              value: eur(cycle['billed_total'] as num?),
              gradient: kGradBrand,
            ),
          ],
        ),
        const SizedBox(height: 11),
        KpiSectionCard(
          icon: '↔',
          iconColor: kMuted,
          title: 'Écarts du cycle',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _gapRow(
                _label(labels, 'gap_ordered_received', 'Écart commandé → reçu'),
                cycle['gap_ordered_received'] as num?,
              ),
              _gapRow(
                _label(labels, 'gap_billed_received', 'Écart facturé → reçu'),
                cycle['gap_billed_received'] as num?,
              ),
              _gapRow(
                _label(labels, 'missing_value', 'En attente de livraison'),
                cycle['missing_value'] as num?,
              ),
            ],
          ),
        ),

        const SizedBox(height: 18),
        const _Section('Prix'),
        KpiSectionCard(
          icon: '€',
          iconColor: kWarn,
          title: 'Variations détectées',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(spacing: 14, runSpacing: 6, children: [
                _priceChip('${plainNumber((price['n_hausse'] as num?) ?? 0)} en hausse', kBad),
                _priceChip('${plainNumber((price['n_baisse'] as num?) ?? 0)} en baisse', kGood),
                _priceChip(
                  price['top_inflation_pct'] == null
                      ? 'Pic —'
                      : 'Pic ${pctSigned(price['top_inflation_pct'] as num?)}',
                  kWarn,
                ),
                _priceChip('${plainNumber((price['n_critiques'] as num?) ?? 0)} critiques', kWarn),
                _priceChip(
                  '${eur(price['switch_savings_total'] as num?)} en changeant de fournisseur',
                  kGood,
                ),
              ]),
              const SizedBox(height: 10),
              InkWell(
                borderRadius: BorderRadius.circular(6),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => Scaffold(
                    appBar: AppBar(
                      title: const Text('Variations de prix',
                          style: TextStyle(fontFamily: 'Newsreader')),
                    ),
                    body: const PriceScreen(),
                  ),
                )),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('Voir le détail',
                        style: TextStyle(
                            fontSize: 12.5, fontWeight: FontWeight.w600, color: kTerracotta)),
                    SizedBox(width: 4),
                    Icon(Icons.arrow_forward, size: 14, color: kTerracotta),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Top produits (dépense) — n'apparaît que s'il y a des lignes, comme
        // sur le web (`pilotage-view.tsx`).
        if (topProducts.isNotEmpty) ...[
          const SizedBox(height: 18),
          const _Section('Top produits'),
          KpiSectionCard(
            icon: '📦',
            iconColor: kTerracotta,
            title: 'Top produits (dépense)',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final raw in topProducts)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text('${(raw as Map)['name'] ?? '—'}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                        ),
                        Text(eur(raw['total_spend'] as num?),
                            style: const TextStyle(
                                fontSize: 12.5, color: kMuted, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],

        const SizedBox(height: 18),
        const _Section('Fournisseurs'),
        _SupplierList(
          icon: '★',
          iconColor: kGood,
          title: _label(labels, 'most_competitive', 'Plus compétitifs'),
          items: _list(suppliers['most_competitive']),
          empty: 'Pas encore assez de données.',
          valueOf: (s) => eur((s as Map)['realized'] as num?),
        ),
        const SizedBox(height: 10),
        _SupplierList(
          icon: '⏰',
          iconColor: kWarn,
          title: _label(labels, 'most_late', 'En retard'),
          items: _list(suppliers['most_late']),
          empty: 'Aucun retard détecté.',
          valueOf: (s) =>
              '${plainNumber(((s as Map)['late_count'] as num?) ?? 0)} livraison(s)',
        ),
        const SizedBox(height: 10),
        _SupplierList(
          icon: '✓',
          iconColor: kGood,
          title: _label(labels, 'best_conformity', 'Meilleure conformité'),
          items: _list(suppliers['best_conformity']),
          empty: 'Pas encore assez de données.',
          valueOf: (s) {
            final r = (s as Map)['conformity_rate'] as num?;
            return r == null ? '—' : '${(r * 100).round()} %';
          },
        ),
      ],
    );
  }

  Widget _gapRow(String label, num? v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(
              child: Text(label,
                  style: const TextStyle(fontSize: 12.5, color: kMuted))),
            Text(eur(v), style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
          ],
        ),
      );

  Widget _priceChip(String text, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: .12),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(text, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: color)),
      );
}

class _Section extends StatelessWidget {
  const _Section(this.title, {this.caption});
  final String title;
  final String? caption;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(title, style: kSerif.copyWith(fontSize: 16, fontWeight: FontWeight.w700)),
            if (caption != null) ...[
              const SizedBox(width: 6),
              Text('· $caption', style: const TextStyle(fontSize: 12, color: kMuted)),
            ],
          ],
        ),
      );
}

/// Une des trois listes fournisseurs (compétitivité / retards / conformité) —
/// équivalent mobile de `SupplierListCard` côté web (`pilotage-view.tsx`).
class _SupplierList extends StatelessWidget {
  const _SupplierList({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.items,
    required this.empty,
    required this.valueOf,
  });
  final String icon, title, empty;
  final Color iconColor;
  final List<dynamic> items;
  final String Function(dynamic item) valueOf;

  @override
  Widget build(BuildContext context) {
    return KpiSectionCard(
      icon: icon,
      iconColor: iconColor,
      title: title,
      child: items.isEmpty
          ? Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Text(empty, style: const TextStyle(fontSize: 12.5, color: kMuted)),
            )
          : Column(
              children: [
                for (final raw in items)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text('${(raw as Map)['name'] ?? '—'}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                        ),
                        Text(valueOf(raw),
                            style: const TextStyle(
                                fontSize: 12.5, color: kMuted, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ),
              ],
            ),
    );
  }
}
