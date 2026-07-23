import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad, kTerracotta;
import '../products/product_detail_screen.dart';

/// Comparatif multi-devis (§7) — même moteur que le web (`GET /quotes/matrix`).
///
/// Sur mobile, un tableau à colonnes ne tient pas : on rend **une carte par
/// produit**, listant les offres triées de la meilleure à la plus chère. Les
/// couleurs et les règles restent celles du moteur (vert = meilleure, orange =
/// intermédiaire, rouge = la plus chère, gris = hors classement).
final quoteMatrixProvider =
    FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final resp = await ref
      .read(apiClientProvider)
      .dio
      .get('/quotes/matrix', queryParameters: {'status': 'draft'});
  return Map<String, dynamic>.from(resp.data as Map);
});

({Color bg, Color fg}) _tone(String? rank) {
  switch (rank) {
    case 'best':
      return (bg: const Color(0xFFE3ECDB), fg: kGood);
    case 'worst':
      return (bg: const Color(0xFFF6E1DC), fg: kBad);
    case 'mid':
      return (bg: const Color(0xFFF6EAD4), fg: kWarn);
    default:
      return (bg: const Color(0xFFECE6DA), fg: kMuted);
  }
}

String _num(dynamic v, {int digits = 2}) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  if (n == null) return '$v';
  return n.toStringAsFixed(digits).replaceAll('.', ',');
}

class QuoteMatrixScreen extends ConsumerWidget {
  const QuoteMatrixScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(quoteMatrixProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Comparatif des devis',
            style: TextStyle(fontFamily: 'Newsreader')),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(quoteMatrixProvider);
          await ref.read(quoteMatrixProvider.future);
        },
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Center(child: Text(apiErrorMessage(e))),
            ),
          ]),
          data: (m) {
            final products =
                (m['products'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
            if (products.isEmpty) {
              return ListView(children: const [
                SizedBox(height: 120),
                Icon(Icons.table_chart_outlined, size: 40, color: kMuted),
                SizedBox(height: 12),
                Center(
                  child: Text(
                    'Aucun devis en cours à comparer.\nImportez un devis pour commencer.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: kMuted),
                  ),
                ),
              ]);
            }
            final suppliers =
                (m['suppliers'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
            final names = {
              for (final s in suppliers) '${s['supplier_id']}': s['supplier_name']
            };
            return ListView(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 24),
              children: [
                _summary(m, names),
                const SizedBox(height: 12),
                for (final p in products) _productCard(context, p),
                const SizedBox(height: 8),
                _legend(),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _summary(Map<String, dynamic> m, Map<String, dynamic> names) {
    final cheapest = names['${m['cheapest_supplier_id']}'];
    final fastest = names['${m['fastest_supplier_id']}'];
    final savings = m['potential_savings'] as num?;
    Widget tile(IconData icon, Color color, String value, String label) => Expanded(
          child: MockCard(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(icon, size: 18, color: color),
              const SizedBox(height: 6),
              Text(value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
              Text(label, style: const TextStyle(fontSize: 11, color: kMuted)),
            ]),
          ),
        );
    return Row(children: [
      tile(Icons.emoji_events_outlined, kGood, '${cheapest ?? '—'}', 'Le moins cher'),
      const SizedBox(width: 8),
      tile(Icons.local_shipping_outlined, kTerracotta, '${fastest ?? '—'}', 'Le plus rapide'),
      const SizedBox(width: 8),
      tile(Icons.savings_outlined, kWarn, eur(savings), 'Économies'),
    ]);
  }

  Widget _productCard(BuildContext context, Map<String, dynamic> p) {
    final offers = (p['offers'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    // meilleure -> intermédiaire -> plus chère -> hors classement
    const order = {'best': 0, 'mid': 1, 'worst': 2};
    final sorted = [...offers]
      ..sort((a, b) => (order[a['rank']] ?? 9).compareTo(order[b['rank']] ?? 9));
    final basis = p['basis'] == 'base_unit';
    final unit = offers.firstWhere(
      (o) => o['base_unit'] != null,
      orElse: () => const {},
    )['base_unit'];
    final history = (p['history'] as Map?) ?? const {};
    final vsLast = p['vs_last_paid_pct'] as num?;

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: MockCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          InkWell(
            onTap: p['product_id'] != null
                ? () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => ProductDetailScreen(
                        productId: '${p['product_id']}',
                        productName: '${p['product_name'] ?? 'Produit'}',
                      ),
                    ))
                : null,
            child: Text('${p['product_name'] ?? 'Produit'}',
                style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
          ),
          const SizedBox(height: 2),
          Wrap(spacing: 8, children: [
            Text(basis ? 'prix / $unit' : 'prix affiché',
                style: TextStyle(fontSize: 11.5, color: basis ? kMuted : kWarn)),
            if (!basis)
              const Text('conditionnements non comparables',
                  style: TextStyle(fontSize: 11.5, color: kWarn)),
            if (history['last_paid'] != null)
              Text(
                'payé ${eur(history['last_paid'] as num?)}'
                '${vsLast != null ? '  ${vsLast > 0 ? '+' : ''}${_num(vsLast, digits: 1)} %' : ''}',
                style: TextStyle(
                  fontSize: 11.5,
                  color: vsLast == null ? kMuted : (vsLast <= 0 ? kGood : kBad),
                ),
              ),
          ]),
          const SizedBox(height: 8),
          for (final o in sorted) _offerRow(o, basis),
        ]),
      ),
    );
  }

  Widget _offerRow(Map<String, dynamic> o, bool basis) {
    final tone = _tone(o['rank'] as String?);
    final price = basis ? o['price_per_base_unit'] : o['unit_price'];
    final delta = o['delta_pct_vs_best'] as num?;
    final expired = o['expired'] == true;
    final unavailable = o['available'] == false;
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration:
          BoxDecoration(color: tone.bg, borderRadius: BorderRadius.circular(10)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text('${o['supplier_name'] ?? 'Fournisseur'}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          ),
          Text(eur(price as num?),
              style: TextStyle(
                  fontSize: 14, fontWeight: FontWeight.w700, color: tone.fg)),
          if (delta != null && delta > 0)
            Padding(
              padding: const EdgeInsets.only(left: 6),
              child: Text('+${_num(delta, digits: 1)} %',
                  style: TextStyle(fontSize: 11.5, color: tone.fg)),
            ),
        ]),
        const SizedBox(height: 2),
        Text(
          [
            if (o['unit_price'] != null)
              '${eur(o['unit_price'] as num?)} / ${o['pack_size'] ?? 'unité'}',
            if (o['vat_rate'] != null) 'TVA ${_num(o['vat_rate'], digits: 1)} %',
            if (o['discount_pct'] != null) '−${_num(o['discount_pct'], digits: 1)} %',
            if (o['lead_time_days'] != null) '${o['lead_time_days']} j',
          ].join('  ·  '),
          style: const TextStyle(fontSize: 11.5, color: kMuted),
        ),
        if (expired || unavailable)
          Padding(
            padding: const EdgeInsets.only(top: 3),
            child: Text(expired ? 'Offre périmée' : 'Indisponible',
                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: kBad)),
          ),
      ]),
    );
  }

  Widget _legend() => const Padding(
        padding: EdgeInsets.symmetric(horizontal: 4),
        child: Text(
          'Vert : meilleure offre · orange : intermédiaire · rouge : la plus chère · '
          'gris : hors classement (périmée ou indisponible).',
          style: TextStyle(fontSize: 11, color: kMuted),
        ),
      );
}
