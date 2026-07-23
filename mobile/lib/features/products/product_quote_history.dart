import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kBad;

/// Les offres reçues pour un produit (§10) — pendant mobile de la carte web.
///
/// À côté de l'historique d'ACHAT, qui dit ce qui a été payé. Ces prix-là ont
/// seulement été *proposés* : ils n'entrent pas dans le coût de revient (un food
/// cost calculé sur un prix jamais payé serait faux), mais ils servent à
/// négocier.
final productQuoteHistoryProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, String>((ref, id) async {
  final resp =
      await ref.read(apiClientProvider).dio.get('/products/$id/quote-history');
  return Map<String, dynamic>.from(resp.data as Map);
});

String _num(dynamic v, {int digits = 1}) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  return n == null ? '$v' : n.toStringAsFixed(digits).replaceAll('.', ',');
}

class ProductQuoteHistorySection extends ConsumerWidget {
  const ProductQuoteHistorySection({super.key, required this.productId});
  final String productId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(productQuoteHistoryProvider(productId));
    return async.maybeWhen(
      orElse: () => const SizedBox.shrink(),
      data: (data) {
        final offers = (data['offers'] as List? ?? const [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        // Sans devis reçu, pas de section : un bloc vide n'apprend rien.
        if (offers.isEmpty) return const SizedBox.shrink();

        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const SizedBox(height: 16),
          const Text('Devis reçus',
              style: TextStyle(
                  fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
          const Text(
            'Prix proposés — ils n\'entrent pas dans le coût de revient.',
            style: TextStyle(fontSize: 12, color: kMuted),
          ),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: [
            _stat('Meilleure', eur(data['best_price'] as num?),
                sub: '${data['best_supplier_name'] ?? ''}'),
            _stat('Dernière', eur(data['latest_price'] as num?)),
            _stat('Moyenne', eur(data['avg_price'] as num?),
                sub: '${data['count']} offre(s)'),
          ]),
          const SizedBox(height: 8),
          for (final o in offers) _offerTile(o),
        ]);
      },
    );
  }

  Widget _stat(String k, String v, {String? sub}) => Container(
        width: 150,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFFECE4D4)),
            borderRadius: BorderRadius.circular(10)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(k, style: const TextStyle(fontSize: 11.5, color: kMuted)),
          const SizedBox(height: 2),
          Text(v, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          if (sub != null && sub.isNotEmpty)
            Text(sub,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 11, color: kMuted)),
        ]),
      );

  Widget _offerTile(Map<String, dynamic> o) {
    final delta = o['delta_pct_vs_previous'] as num?;
    final detail = [
      if (o['date'] != null) '${o['date']}',
      if (o['pack_size'] != null) '${o['pack_size']}',
      if (o['brand'] != null) '${o['brand']}',
      if (o['min_qty'] != null) 'min. ${_num(o['min_qty'], digits: 0)}',
    ].join(' · ');
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Row(children: [
          Flexible(
            child: Text('${o['supplier_name'] ?? '—'}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
          ),
          if (o['is_best'] == true)
            const Padding(
              padding: EdgeInsets.only(left: 4),
              child: Icon(Icons.emoji_events_outlined, size: 15, color: kGood),
            ),
        ]),
        subtitle: Text(detail.isEmpty ? '—' : detail,
            style: const TextStyle(fontSize: 12.5, color: kMuted)),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(eur(o['net_unit_price'] as num?),
                style: const TextStyle(fontWeight: FontWeight.w600)),
            if (delta != null)
              Text('${delta > 0 ? '+' : ''}${_num(delta)} %',
                  style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: delta > 0 ? kBad : kGood)),
          ],
        ),
      ),
    );
  }
}
