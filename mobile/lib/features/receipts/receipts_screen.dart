import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood;
import 'receipt_detail_screen.dart';

/// Les réceptions — pendant mobile de `/receptions` sur le web.
final receiptsListProvider =
    FutureProvider.autoDispose.family<Loaded, String?>((ref, orderId) async {
  // Cache hors-ligne comme les autres listes : une réception se consulte en
  // réserve, là où le réseau est le plus mauvais.
  return fetchWithCache(
    ref,
    cacheKey: 'receipts-${orderId ?? 'all'}',
    request: () async {
      final resp = await ref.read(apiClientProvider).dio.get(
            '/receipts/',
            queryParameters: orderId == null ? null : {'order_id': orderId},
          );
      return resp.data;
    },
  );
});

/// Le vocabulaire du contrôle qualité vient du serveur : web et mobile n'en
/// tiennent aucune copie, qui finirait par diverger.
final qualityVocabularyProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/receipts/quality-checks');
  return Map<String, dynamic>.from(resp.data as Map);
});

class ReceiptsScreen extends ConsumerWidget {
  const ReceiptsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: offlineCardList(
        ref: ref,
        provider: receiptsListProvider(null),
        empty: 'Aucune réception. Elles se créent depuis une commande, à la livraison.',
        itemBuilder: (r) => _ReceiptCard(receipt: Map<String, dynamic>.from(r as Map)),
      ),
    );
  }
}

class _ReceiptCard extends StatelessWidget {
  const _ReceiptCard({required this.receipt});
  final Map<String, dynamic> receipt;

  @override
  Widget build(BuildContext context) {
    final frozen = receipt['status'] == 'checked';
    return GestureDetector(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => ReceiptDetailScreen(
          receiptId: '${receipt['id']}',
          reference: receipt['reference'] as String?,
        ),
      )),
      child: MockCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text('${receipt['reference'] ?? 'Réception'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: (frozen ? kGood : kMuted).withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                if (frozen)
                  const Padding(
                    padding: EdgeInsets.only(right: 3),
                    child: Icon(Icons.verified_outlined, size: 12, color: kGood),
                  ),
                Text('${receipt['status_label'] ?? ''}',
                    style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                        color: frozen ? kGood : kMuted)),
              ]),
            ),
          ]),
          const SizedBox(height: 4),
          Text(
            [
              '${receipt['supplier_name'] ?? 'Fournisseur'}',
              if (receipt['order_reference'] != null) '${receipt['order_reference']}',
              '${receipt['line_count'] ?? 0} ligne(s)',
              if (receipt['received_at'] != null) '${receipt['received_at']}',
            ].join('  ·  '),
            style: const TextStyle(fontSize: 12.5, color: kMuted),
          ),
          if (receipt['received_by_name'] != null) ...[
            const SizedBox(height: 2),
            Text('par ${receipt['received_by_name']}',
                style: const TextStyle(fontSize: 11.5, color: kMuted)),
          ],
        ]),
      ),
    );
  }
}
