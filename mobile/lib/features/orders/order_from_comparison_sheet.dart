import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kWarn;
import 'order_detail_screen.dart';
import 'orders_screen.dart' show ordersListProvider;

/// « Commander le moins cher » — pendant mobile du dialogue web.
///
/// Le comparateur désigne le meilleur prix **produit par produit**, donc
/// souvent chez plusieurs fournisseurs. Cette feuille montre la répartition
/// réelle — une commande par fournisseur, avec son port et son total — avant
/// d'engager quoi que ce soit : découvrir après coup qu'on s'est trompé de
/// lignes coûterait autant d'annulations.
Future<void> showOrderFromComparison(
  BuildContext context,
  WidgetRef ref,
  List<String> quoteLineIds,
) async {
  if (quoteLineIds.isEmpty) return;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _Sheet(quoteLineIds: quoteLineIds),
  );
}

class _Sheet extends ConsumerStatefulWidget {
  const _Sheet({required this.quoteLineIds});
  final List<String> quoteLineIds;
  @override
  ConsumerState<_Sheet> createState() => _SheetState();
}

class _SheetState extends ConsumerState<_Sheet> {
  List<Map<String, dynamic>>? _plans;
  String? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final resp = await ref.read(apiClientProvider).dio.post(
            '/orders/plan',
            data: {'quote_line_ids': widget.quoteLineIds},
          );
      if (!mounted) return;
      setState(() => _plans = ((resp.data as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList());
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _confirm(String status) async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    setState(() => _saving = true);
    try {
      final resp = await ref.read(apiClientProvider).dio.post(
            '/orders/from-quote-lines',
            data: {'quote_line_ids': widget.quoteLineIds, 'status': status},
          );
      final data = Map<String, dynamic>.from(resp.data as Map);
      final orders =
          (data['orders'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
      ref.invalidate(ordersListProvider(null));
      navigator.pop();
      messenger.showSnackBar(SnackBar(
        content: Text(data['order_count'] == 1
            ? 'Commande créée'
            : '${data['order_count']} commandes créées chez '
                '${data['supplier_count']} fournisseurs'),
      ));
      // Une seule commande : on l'ouvre. Plusieurs : on reste, sinon on
      // choisirait arbitrairement laquelle montrer.
      if (orders.length == 1) {
        navigator.push(MaterialPageRoute(
          builder: (_) => OrderDetailScreen(
            orderId: '${orders.first['id']}',
            reference: orders.first['reference'] as String?,
          ),
        ));
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final plans = _plans;
    final total = (plans ?? []).fold<double>(
        0, (s, p) => s + ((p['total_amount'] as num?)?.toDouble() ?? 0));

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFE7DFCF),
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          const SizedBox(height: 12),
          const Align(
            alignment: Alignment.centerLeft,
            child: Text('Commander les meilleures offres',
                style: TextStyle(
                    fontFamily: 'Newsreader', fontSize: 19, fontWeight: FontWeight.w700)),
          ),
          const SizedBox(height: 2),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '${widget.quoteLineIds.length} offre(s) retenue(s) — une commande par fournisseur.',
              style: const TextStyle(fontSize: 12.5, color: kMuted),
            ),
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Text(_error!, style: const TextStyle(fontSize: 13, color: kWarn))
          else if (plans == null)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: CircularProgressIndicator(),
            )
          else ...[
            ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: MediaQuery.of(context).size.height * 0.42,
              ),
              child: ListView(shrinkWrap: true, children: [
                for (final p in plans) _planCard(p),
              ]),
            ),
            const SizedBox(height: 8),
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('Total engagé · ${plans.length} commande(s)',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              Text(eur(total),
                  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving ? null : () => _confirm('draft'),
                  child: const Text('Brouillon'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                flex: 2,
                child: GradientButton(
                  label: 'Commander',
                  onPressed: _saving ? null : () => _confirm('sent'),
                  expand: true,
                  loading: _saving,
                ),
              ),
            ]),
          ],
        ]),
      ),
    );
  }

  Widget _planCard(Map<String, dynamic> p) {
    final lines = (p['lines'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final fee = p['delivery_fee'] as num?;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: MockCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text('${p['supplier_name'] ?? 'Fournisseur'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
            ),
            Text(eur(p['total_amount'] as num?),
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 2),
          Text(
            [
              '${lines.length} ligne(s)',
              'panier ${eur(p['lines_total'] as num?)}',
              if (fee != null && fee > 0) '+${eur(fee)} de port',
            ].join('  ·  '),
            style: TextStyle(
                fontSize: 11.5, color: (fee != null && fee > 0) ? kWarn : kMuted),
          ),
          const SizedBox(height: 4),
          for (final l in lines.take(4))
            Text(
              '${l['description'] ?? 'Ligne'} — ${eur(l['line_total'] as num?)}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11.5, color: kMuted),
            ),
          if (lines.length > 4)
            Text('+ ${lines.length - 4} autre(s)',
                style: const TextStyle(fontSize: 11.5, color: kMuted)),
        ]),
      ),
    );
  }
}
