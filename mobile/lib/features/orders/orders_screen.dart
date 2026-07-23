import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad, kTerracotta;
import 'order_detail_screen.dart';

/// Les commandes fournisseur — pendant mobile de `/commandes` sur le web.
///
/// Le module existe parce que la commande a cessé d'être un statut sur le
/// devis : c'est un engagement, avec ses dix états et son propre suivi.
final ordersListProvider =
    FutureProvider.autoDispose.family<Loaded, String?>((ref, status) async {
  // Passe par le cache hors-ligne comme les autres listes : une commande en
  // cours est exactement ce qu'on veut consulter en réserve, sans réseau.
  return fetchWithCache(
    ref,
    cacheKey: 'orders-${status ?? 'all'}',
    request: () async {
      final resp = await ref.read(apiClientProvider).dio.get(
            '/orders/',
            queryParameters: status == null ? null : {'status': status},
          );
      return resp.data;
    },
  );
});

/// Les libellés viennent du serveur : web et mobile ne tiennent pas chacun
/// leur table de traduction, qui finiraient par diverger.
final orderStatusesProvider = FutureProvider<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/orders/statuses');
  return (resp.data as List?) ?? const [];
});

/// Le ton d'un état : ce qui attend une action de notre côté ressort.
Color orderStatusColor(String? status) {
  switch (status) {
    case 'partially_received':
      return kWarn;
    case 'received':
    case 'invoiced':
    case 'closed':
      return kGood;
    case 'cancelled':
      return kBad;
    case 'draft':
      return kMuted;
    default:
      return kTerracotta;
  }
}

class OrdersScreen extends ConsumerStatefulWidget {
  const OrdersScreen({super.key});
  @override
  ConsumerState<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends ConsumerState<OrdersScreen> {
  String? _status;

  @override
  Widget build(BuildContext context) {
    final statuses = ref.watch(orderStatusesProvider);
    return Scaffold(
      body: Column(children: [
        SizedBox(
          height: 46,
          child: statuses.maybeWhen(
            orElse: () => const SizedBox.shrink(),
            data: (list) => ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                _chip('Toutes', _status == null, () => setState(() => _status = null)),
                for (final s in list.cast<Map<String, dynamic>>())
                  _chip('${s['label']}', _status == s['value'],
                      () => setState(() => _status = '${s['value']}')),
              ],
            ),
          ),
        ),
        Expanded(
          child: offlineCardList(
            ref: ref,
            provider: ordersListProvider(_status),
            empty: _status == null
                ? 'Aucune commande. Comparez vos devis et commandez les meilleures offres.'
                : 'Aucune commande dans cet état.',
            itemBuilder: (o) => _OrderCard(order: Map<String, dynamic>.from(o as Map)),
          ),
        ),
      ]),
    );
  }

  Widget _chip(String label, bool selected, VoidCallback onTap) => Padding(
        padding: const EdgeInsets.only(right: 6, top: 6, bottom: 6),
        child: ChoiceChip(
          label: Text(label, style: const TextStyle(fontSize: 12.5)),
          selected: selected,
          onSelected: (_) => onTap(),
        ),
      );
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({required this.order});
  final Map<String, dynamic> order;

  @override
  Widget build(BuildContext context) {
    final tone = orderStatusColor(order['status'] as String?);
    return GestureDetector(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => OrderDetailScreen(
          orderId: '${order['id']}',
          reference: order['reference'] as String?,
        ),
      )),
      child: MockCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text('${order['reference'] ?? 'Commande'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: tone.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text('${order['status_label'] ?? order['status'] ?? ''}',
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: tone)),
            ),
          ]),
          const SizedBox(height: 4),
          Text(
            [
              '${order['supplier_name'] ?? 'Fournisseur'}',
              '${order['line_count'] ?? 0} ligne(s)',
              if (order['expected_date'] != null) 'attendue le ${order['expected_date']}',
            ].join('  ·  '),
            style: const TextStyle(fontSize: 12.5, color: kMuted),
          ),
          const SizedBox(height: 6),
          Row(children: [
            Text(eur(order['total_amount'] as num?),
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            if ((order['delivery_fee'] as num?) != null &&
                (order['delivery_fee'] as num) > 0) ...[
              const SizedBox(width: 8),
              Text('dont ${eur(order['delivery_fee'] as num?)} de port',
                  style: const TextStyle(fontSize: 11.5, color: kWarn)),
            ],
          ]),
        ]),
      ),
    );
  }
}
