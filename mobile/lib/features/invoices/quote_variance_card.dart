import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad;

/// Contrôle prévu / facturé (§9) — pendant mobile de la carte web.
///
/// Ne s'affiche QUE si un devis est rattaché à la facture : un bloc vide
/// laisserait croire à un contrôle là où il n'y a rien à contrôler. Et quand la
/// facture est conforme, un bandeau d'une ligne suffit — inutile de dérouler
/// 40 lignes vertes.
final invoiceVarianceProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, String>((ref, invoiceId) async {
  final resp = await ref
      .read(apiClientProvider)
      .dio
      .get('/invoices/$invoiceId/quote-variance');
  return Map<String, dynamic>.from(resp.data as Map);
});

const _labels = {
  'ok': 'Conforme',
  'price_up': 'Prix en hausse',
  'price_down': 'Prix en baisse',
  'qty_diff': 'Quantité différente',
  'missing': 'Non facturé',
  'extra': 'Hors devis',
};

({Color bg, Color fg}) _tone(String? status) {
  switch (status) {
    case 'price_up':
    case 'extra':
      return (bg: const Color(0xFFF6E1DC), fg: kBad);
    case 'price_down':
      return (bg: const Color(0xFFE3ECDB), fg: kGood);
    case 'qty_diff':
    case 'missing':
      return (bg: const Color(0xFFF6EAD4), fg: kWarn);
    default:
      return (bg: const Color(0xFFECE6DA), fg: kMuted);
  }
}

String _n(dynamic v, {int digits = 1}) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  return n == null ? '$v' : n.toStringAsFixed(digits).replaceAll('.', ',');
}

class QuoteVarianceCard extends ConsumerWidget {
  const QuoteVarianceCard({super.key, required this.invoiceId});
  final String invoiceId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(invoiceVarianceProvider(invoiceId));
    return async.maybeWhen(
      orElse: () => const SizedBox.shrink(),
      data: (v) {
        if (v['linked'] != true) return const SizedBox.shrink();
        final conform = v['is_conform'] == true;
        final delta = (v['total_delta'] as num?) ?? 0;
        final lines = (v['lines'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
        final issues = lines
            .where((l) => l['status'] != 'ok' || l['vat_mismatch'] == true)
            .toList();

        return Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Icon(conform ? Icons.verified_outlined : Icons.warning_amber_rounded,
                      size: 18, color: conform ? kGood : kWarn),
                  const SizedBox(width: 6),
                  const Expanded(
                    child: Text('Contrôle devis / facture',
                        style: TextStyle(
                            fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
                  ),
                  if (v['quote_reference'] != null)
                    Text('${v['quote_reference']}',
                        style: const TextStyle(fontSize: 12, color: kMuted)),
                ]),
                const SizedBox(height: 4),
                Text(
                  conform
                      ? 'La facture est conforme au devis accepté.'
                      : '${v['issue_count']} ligne(s) s\'écartent du devis — '
                          '${delta > 0 ? '+' : ''}${eur(delta)}'
                          '${v['total_delta_pct'] != null ? ' (${delta > 0 ? '+' : ''}${_n(v['total_delta_pct'])} %)' : ''}'
                          ' sur ${eur(v['quoted_total'] as num?)} devisés.',
                  style: TextStyle(
                    fontSize: 13,
                    color: conform ? kMuted : (delta > 0 ? kBad : kGood),
                    fontWeight: conform ? FontWeight.w400 : FontWeight.w600,
                  ),
                ),
                if (issues.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  for (final l in issues) _issueRow(l),
                ],
              ]),
            ),
          ),
        );
      },
    );
  }

  Widget _issueRow(Map<String, dynamic> l) {
    final tone = _tone(l['status'] as String?);
    final q = (l['quoted'] as Map?) ?? const {};
    final b = (l['billed'] as Map?) ?? const {};
    final totalDelta = l['total_delta'] as num?;
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(color: tone.bg, borderRadius: BorderRadius.circular(10)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text('${l['product_name'] ?? 'Ligne'}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          ),
          Text(_labels[l['status']] ?? '${l['status']}',
              style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: tone.fg)),
          if (totalDelta != null && totalDelta != 0)
            Padding(
              padding: const EdgeInsets.only(left: 8),
              child: Text('${totalDelta > 0 ? '+' : ''}${eur(totalDelta)}',
                  style: TextStyle(
                      fontSize: 13, fontWeight: FontWeight.w700, color: tone.fg)),
            ),
        ]),
        const SizedBox(height: 3),
        Text(
          'Devisé ${eur(q['unit_price'] as num?)}'
          '${q['qty'] != null ? ' × ${_n(q['qty'], digits: 0)}' : ''}'
          '   →   Facturé ${eur(b['unit_price'] as num?)}'
          '${b['qty'] != null ? ' × ${_n(b['qty'], digits: 0)}' : ''}'
          '${l['price_delta_pct'] != null ? '  (${(l['price_delta_pct'] as num) > 0 ? '+' : ''}${_n(l['price_delta_pct'])} %)' : ''}',
          style: const TextStyle(fontSize: 11.5, color: kMuted),
        ),
        if (l['vat_mismatch'] == true)
          Padding(
            padding: const EdgeInsets.only(top: 3),
            child: Text(
              'TVA ${_n(q['vat_rate'])} % → ${_n(b['vat_rate'])} %',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: kWarn),
            ),
          ),
      ]),
    );
  }
}
