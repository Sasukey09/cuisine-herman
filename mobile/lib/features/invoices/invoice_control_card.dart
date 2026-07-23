import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad;

/// Contrôle facture (commandé → livré → facturé) — pendant mobile de la carte
/// web. Remplace l'ancienne carte d'écarts devis/facture (§9), morte depuis que
/// la commande est un objet à part entière.
///
/// L'app iOS déjà en production appelle encore `/quote-variance` ; le serveur le
/// sert comme un alias du nouveau `/control`, donc cette carte peut utiliser
/// directement `/control`.
final invoiceControlProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, String>((ref, invoiceId) async {
  final resp = await ref
      .read(apiClientProvider)
      .dio
      .get('/invoices/$invoiceId/control');
  return Map<String, dynamic>.from(resp.data as Map);
});

const _flagLabels = {
  'billed_not_received': 'Facturé mais non reçu',
  'extra': 'Facturé hors commande',
  'over_billed': 'Facturé plus que reçu',
  'not_received': 'Commandé, pas encore reçu',
  'price_up': 'Prix en hausse',
  'vat_diff': 'TVA différente',
  'qty_diff': 'Quantité différente du reçu',
  'price_down': 'Prix en baisse',
  'missing': 'Reçu mais pas encore facturé',
};

// On paie une marchandise qu'on n'a pas : le rouge est réservé à ces cas-là.
const _grave = {'billed_not_received', 'over_billed', 'extra'};

Color _rowColor(String status) {
  if (_grave.contains(status)) return kBad;
  if (status == 'price_down' || status == 'missing') return kGood;
  return kWarn;
}

String _n(dynamic v, {int digits = 0}) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  return n == null ? '$v' : n.toStringAsFixed(digits).replaceAll('.', ',');
}

class InvoiceControlCard extends ConsumerWidget {
  const InvoiceControlCard({super.key, required this.invoiceId});
  final String invoiceId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(invoiceControlProvider(invoiceId));
    return async.maybeWhen(
      orElse: () => const SizedBox.shrink(),
      data: (data) {
        if (data['linked'] != true) return const SizedBox.shrink();
        final conform = data['is_conform'] == true;
        final grave = data['billed_not_received_count'] as int? ?? 0;
        final delta = (data['total_delta'] as num?) ?? 0;
        final lines =
            (data['lines'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
        final issues = lines.where((l) => l['status'] != 'ok').toList();

        return Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Icon(
                    conform
                        ? Icons.verified_outlined
                        : grave > 0
                            ? Icons.gpp_maybe_outlined
                            : Icons.warning_amber_rounded,
                    size: 18,
                    color: conform ? kGood : (grave > 0 ? kBad : kWarn),
                  ),
                  const SizedBox(width: 6),
                  const Expanded(
                    child: Text('Contrôle commande → livraison → facture',
                        style: TextStyle(
                            fontFamily: 'Newsreader',
                            fontSize: 16,
                            fontWeight: FontWeight.w700)),
                  ),
                  if (data['order_reference'] != null)
                    Text('${data['order_reference']}',
                        style: const TextStyle(fontSize: 12, color: kMuted)),
                ]),
                const SizedBox(height: 4),
                Text(
                  conform
                      ? 'La facture est fidèle à ce qui a été commandé et livré.'
                      : '${data['issue_count']} ligne(s) s\'écartent'
                          '${delta != 0 ? ' — ${delta > 0 ? '+' : ''}${eur(delta)} vs commandé' : ''}'
                          '${grave > 0 ? ' · $grave facturée(s) sans être reçue(s)' : ''}',
                  style: TextStyle(
                    fontSize: 13,
                    color: conform ? kMuted : (grave > 0 ? kBad : kWarn),
                    fontWeight: conform ? FontWeight.w400 : FontWeight.w600,
                  ),
                ),
                if (!conform) ...[
                  const SizedBox(height: 10),
                  for (final l in issues) _row(l),
                ],
              ]),
            ),
          ),
        );
      },
    );
  }

  Widget _row(Map<String, dynamic> l) {
    final status = '${l['status']}';
    final tone = _rowColor(status);
    final flags = (l['flags'] as List?)?.cast<String>() ?? const [];
    final o = l['ordered'] as Map?;
    final r = l['received'] as Map?;
    final b = l['billed'] as Map?;

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text('${l['description'] ?? 'Ligne'}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          ),
          Text(flags.map((f) => _flagLabels[f] ?? f).join(' · '),
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: tone)),
        ]),
        const SizedBox(height: 3),
        // Les trois colonnes en une ligne : c'est la lecture du module.
        Text(
          'commandé ${o != null ? '${_n(o['qty'])} × ${eur(o['unit_price'] as num?)}' : '—'}'
          '   ·   livré ${r != null ? _n(r['qty']) : '—'}'
          '   ·   facturé ${b != null ? '${_n(b['qty'])} × ${eur(b['unit_price'] as num?)}' : '—'}',
          style: const TextStyle(fontSize: 11.5, color: kMuted),
        ),
      ]),
    );
  }
}
