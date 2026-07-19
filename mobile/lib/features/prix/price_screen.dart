import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kBad, kGood, kWarn;

final _priceDashProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/price-variations');
  return (resp.data as Map).cast<String, dynamic>();
});

final _priceAlertsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/alerts/prices');
  return resp.data as List<dynamic>;
});

class PriceScreen extends ConsumerWidget {
  const PriceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dash = ref.watch(_priceDashProvider);
    final alerts = ref.watch(_priceAlertsProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(_priceDashProvider);
        ref.invalidate(_priceAlertsProvider);
        await Future.wait([
          ref.read(_priceDashProvider.future),
          ref.read(_priceAlertsProvider.future),
        ]);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
        children: [
          dash.when(
            loading: () => const _Loading(),
            error: (e, _) => ErrorState(onRetry: () => ref.invalidate(_priceDashProvider)),
            data: (d) {
              final up = (d['most_increased'] as List?) ?? const [];
              final down = (d['most_decreased'] as List?) ?? const [];
              return Column(
                children: [
                  _MoveCard(title: 'Plus fortes hausses', rows: up, up: true),
                  const SizedBox(height: 13),
                  _MoveCard(title: 'Plus fortes baisses', rows: down, up: false),
                ],
              );
            },
          ),
          const SizedBox(height: 13),
          alerts.when(
            loading: () => const _Loading(),
            error: (e, _) => ErrorState(onRetry: () => ref.invalidate(_priceAlertsProvider)),
            data: (rows) => _Card(
              icon: '⚠',
              iconColor: kWarn,
              title: 'Alertes de prix',
              child: rows.isEmpty
                  ? const _EmptyLine('Aucune alerte.')
                  : Column(
                      children: [
                        for (final r in rows.take(12))
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
}

class _MoveCard extends StatelessWidget {
  const _MoveCard({required this.title, required this.rows, required this.up});
  final String title;
  final List<dynamic> rows;
  final bool up;

  @override
  Widget build(BuildContext context) {
    return _Card(
      icon: up ? '▲' : '▼',
      iconColor: up ? kBad : kGood,
      title: title,
      child: rows.isEmpty
          ? _EmptyLine(up ? 'Aucune hausse détectée.' : 'Aucune baisse détectée.')
          : Column(
              children: [
                for (final r in rows.take(6))
                  Builder(builder: (_) {
                    final m = r as Map;
                    final pct = (m['change_pct'] as num?)?.toDouble() ?? 0;
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 7),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text('${m['product_name'] ?? 'Produit'}',
                                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: up ? const Color(0xFFF6E1DC) : const Color(0xFFE3ECDB),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text('${pct > 0 ? '+' : ''}${pct.toStringAsFixed(1)} %',
                                style: TextStyle(
                                    fontSize: 11.5,
                                    fontWeight: FontWeight.w600,
                                    color: up ? kBad : kGood)),
                          ),
                        ],
                      ),
                    );
                  }),
              ],
            ),
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.icon, required this.iconColor, required this.title, required this.child});
  final String icon;
  final Color iconColor;
  final String title;
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
  Widget build(BuildContext context) => const Padding(
      padding: EdgeInsets.all(28), child: Center(child: CircularProgressIndicator()));
}


class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) =>
      Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(text, style: const TextStyle(color: kMuted, fontSize: 12.5)));
}
