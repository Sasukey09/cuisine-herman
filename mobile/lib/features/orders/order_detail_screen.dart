import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kWarn;
import '../auth/auth_controller.dart';
import '../products/product_detail_screen.dart';
import 'orders_screen.dart' show ordersListProvider, orderStatusesProvider, orderStatusColor;

final orderDetailProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/orders/$id');
  return Map<String, dynamic>.from(resp.data as Map);
});

class OrderDetailScreen extends ConsumerWidget {
  const OrderDetailScreen({super.key, required this.orderId, this.reference});
  final String orderId;
  final String? reference;

  Future<void> _setStatus(BuildContext context, WidgetRef ref, String status) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(apiClientProvider).dio.patch('/orders/$orderId', data: {'status': status});
      ref.invalidate(orderDetailProvider(orderId));
      ref.invalidate(ordersListProvider(null));
    } catch (e) {
      // Une transition interdite répond 409 avec les deux libellés en clair :
      // le message du serveur vaut mieux que n'importe quel texte inventé ici.
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(orderDetailProvider(orderId));
    final canWrite = ref.watch(canWriteProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(reference ?? 'Commande',
            style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text(apiErrorMessage(e))),
        data: (order) {
          final lines =
              (order['lines'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
          final anyReceived =
              lines.any((l) => ((l['qty_received'] as num?) ?? 0) > 0);
          return ListView(padding: const EdgeInsets.all(14), children: [
            _header(context, ref, order, canWrite),
            const SizedBox(height: 12),
            const Text('Lignes commandées',
                style: TextStyle(
                    fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
            const Text(
              'Les prix sont ceux du devis retenu. Le reçu se lit dans les réceptions.',
              style: TextStyle(fontSize: 12, color: kMuted),
            ),
            const SizedBox(height: 8),
            for (final l in lines) _line(context, l, anyReceived),
          ]);
        },
      ),
    );
  }

  Widget _header(
      BuildContext context, WidgetRef ref, Map<String, dynamic> order, bool canWrite) {
    final tone = orderStatusColor(order['status'] as String?);
    final statuses = ref.watch(orderStatusesProvider);
    return MockCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text('${order['supplier_name'] ?? 'Fournisseur'}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          ),
          Text(eur(order['total_amount'] as num?),
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 4),
        Text(
          [
            '${order['line_count'] ?? 0} ligne(s)',
            if (order['expected_date'] != null) 'attendue le ${order['expected_date']}',
            if ((order['delivery_fee'] as num?) != null &&
                (order['delivery_fee'] as num) > 0)
              'dont ${eur(order['delivery_fee'] as num?)} de port',
          ].join('  ·  '),
          style: const TextStyle(fontSize: 12.5, color: kMuted),
        ),
        if (order['conditions'] != null) ...[
          const SizedBox(height: 6),
          Text('${order['conditions']}',
              style: const TextStyle(fontSize: 12, color: kMuted)),
        ],
        const SizedBox(height: 10),
        if (canWrite)
          statuses.maybeWhen(
            orElse: () => const SizedBox.shrink(),
            data: (list) => DropdownButtonFormField<String>(
              initialValue: '${order['status']}',
              isDense: true,
              isExpanded: true,
              decoration: const InputDecoration(isDense: true, labelText: 'État'),
              items: [
                for (final s in list.cast<Map<String, dynamic>>())
                  DropdownMenuItem(value: '${s['value']}', child: Text('${s['label']}')),
              ],
              onChanged: (v) => v == null ? null : _setStatus(context, ref, v),
            ),
          )
        else
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: tone.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text('${order['status_label'] ?? ''}',
                style:
                    TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: tone)),
          ),
      ]),
    );
  }

  Widget _line(BuildContext context, Map<String, dynamic> l, bool anyReceived) {
    final ordered = (l['qty_ordered'] as num?) ?? 0;
    final received = (l['qty_received'] as num?) ?? 0;
    final short = received < ordered;
    final productId = l['product_id'] as String?;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: MockCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: GestureDetector(
                onTap: productId == null
                    ? null
                    : () => Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => ProductDetailScreen(
                            productId: productId,
                            productName: '${l['product_name'] ?? l['description'] ?? ''}',
                          ),
                        )),
                child: Text('${l['product_name'] ?? l['description'] ?? 'Ligne'}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      decoration: productId == null ? null : TextDecoration.underline,
                    )),
              ),
            ),
            Text(eur(l['line_total'] as num?),
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 3),
          Text(
            [
              'Qté ${_n(ordered)}',
              if (anyReceived) 'reçu ${_n(received)}',
              'PU ${eur(l['unit_price'] as num?)}',
              if (l['pack_size'] != null) '${l['pack_size']}',
              if (l['brand'] != null) '${l['brand']}',
            ].join('  ·  '),
            style: TextStyle(
              fontSize: 12.5,
              color: anyReceived && short ? kWarn : kMuted,
              fontWeight: anyReceived && short ? FontWeight.w600 : FontWeight.w400,
            ),
          ),
        ]),
      ),
    );
  }

  String _n(num v) => v == v.roundToDouble() ? v.toInt().toString() : '$v';
}
