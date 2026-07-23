import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad;
import '../auth/auth_controller.dart';
import '../orders/orders_screen.dart' show ordersListProvider;
import '../products/product_detail_screen.dart';
import 'receipts_screen.dart' show receiptsListProvider;

final receiptDetailProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/receipts/$id');
  return Map<String, dynamic>.from(resp.data as Map);
});

final receiptControlProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/receipts/$id/control');
  return Map<String, dynamic>.from(resp.data as Map);
});

/// Ce qui ne se lit pas ligne par ligne : le document lui-même.
const _documentAnomalies = {
  'supplier': 'Livré par un autre fournisseur que celui commandé',
};

const _lineAnomalies = {
  'price': 'Prix différent de la commande',
  'pack_size': 'Conditionnement différent',
  'product': 'Produit remplacé',
  'quality': 'Marchandise refusée ou détruite',
  'unordered': 'Livré hors commande',
};

class ReceiptDetailScreen extends ConsumerWidget {
  const ReceiptDetailScreen({super.key, required this.receiptId, this.reference});
  final String receiptId;
  final String? reference;

  Future<void> _validate(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final resp =
          await ref.read(apiClientProvider).dio.post('/receipts/$receiptId/validate');
      final control =
          Map<String, dynamic>.from((resp.data as Map)['control'] as Map);
      ref.invalidate(receiptDetailProvider(receiptId));
      ref.invalidate(receiptControlProvider(receiptId));
      ref.invalidate(receiptsListProvider(null));
      ref.invalidate(ordersListProvider(null));
      final issues = control['issue_count'] as int? ?? 0;
      messenger.showSnackBar(SnackBar(
        content: Text(issues == 0
            ? 'Réception conforme et validée'
            : 'Réception validée · $issues anomalie(s)'),
      ));
    } catch (e) {
      // Une réception déjà validée répond 409 avec son message : l'afficher
      // tel quel vaut mieux qu'un texte inventé ici.
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(receiptDetailProvider(receiptId));
    final control = ref.watch(receiptControlProvider(receiptId));
    final canWrite = ref.watch(canWriteProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(reference ?? 'Réception',
            style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text(apiErrorMessage(e))),
        data: (receipt) {
          final frozen = receipt['status'] == 'checked';
          final lines =
              (receipt['lines'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
          return ListView(padding: const EdgeInsets.all(14), children: [
            _header(receipt, frozen),
            if (control.value != null) ...[
              const SizedBox(height: 10),
              _controlCard(control.value!),
            ],
            const SizedBox(height: 12),
            const Text('Lignes reçues',
                style: TextStyle(
                    fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
            const Text(
              'Accepté, refusé et détruit sont calculés depuis les anomalies.',
              style: TextStyle(fontSize: 12, color: kMuted),
            ),
            const SizedBox(height: 8),
            for (final l in lines) _lineCard(context, l),
            if (canWrite && !frozen) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () => _validate(context, ref),
                  icon: const Icon(Icons.check_circle_outline, size: 18),
                  label: const Text('Valider la réception'),
                ),
              ),
            ],
          ]);
        },
      ),
    );
  }

  Widget _header(Map<String, dynamic> receipt, bool frozen) => MockCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text('${receipt['supplier_name'] ?? 'Fournisseur'}',
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
              child: Text('${receipt['status_label'] ?? ''}',
                  style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: frozen ? kGood : kMuted)),
            ),
          ]),
          const SizedBox(height: 4),
          Text(
            [
              if (receipt['order_reference'] != null) 'commande ${receipt['order_reference']}',
              if (receipt['received_at'] != null) 'reçue le ${receipt['received_at']}',
              if (receipt['delivery_note_number'] != null) 'BL ${receipt['delivery_note_number']}',
            ].join('  ·  '),
            style: const TextStyle(fontSize: 12.5, color: kMuted),
          ),
          // La traçabilité : ce qu'on oppose au fournisseur trois semaines plus
          // tard, quand il conteste un manquant.
          if (receipt['received_by_name'] != null ||
              receipt['checked_by_name'] != null) ...[
            const SizedBox(height: 4),
            Text(
              [
                if (receipt['received_by_name'] != null)
                  'réceptionné par ${receipt['received_by_name']}',
                if (receipt['checked_by_name'] != null)
                  'contrôlé par ${receipt['checked_by_name']}',
                if (receipt['device_info'] != null) 'sur ${receipt['device_info']}',
              ].join('  ·  '),
              style: const TextStyle(fontSize: 11.5, color: kMuted),
            ),
          ],
          if (receipt['notes'] != null) ...[
            const SizedBox(height: 6),
            Text('${receipt['notes']}', style: const TextStyle(fontSize: 12.5)),
          ],
        ]),
      );

  Widget _controlCard(Map<String, dynamic> control) {
    final issues = control['issue_count'] as int? ?? 0;
    if (issues == 0) {
      return const MockCard(
        child: Row(children: [
          Icon(Icons.check_circle_outline, size: 18, color: kGood),
          SizedBox(width: 8),
          Expanded(
            child: Text('Livraison conforme à la commande.',
                style: TextStyle(fontSize: 13)),
          ),
        ]),
      );
    }
    final docAnomalies =
        ((control['document_anomalies'] as List?) ?? const []).cast<String>();
    final lines = (control['lines'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final missing = control['missing_value'] as num? ?? 0;

    return MockCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.warning_amber_rounded, size: 18, color: kWarn),
          const SizedBox(width: 6),
          Expanded(
            child: Text('$issues anomalie(s) au contrôle',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          ),
        ]),
        if (missing > 0)
          Text('${eur(missing)} de marchandise manquante ou refusée.',
              style: const TextStyle(fontSize: 12.5, color: kBad)),
        const SizedBox(height: 6),
        for (final a in docAnomalies)
          Text('• ${_documentAnomalies[a] ?? a}',
              style: const TextStyle(fontSize: 12.5, color: kBad)),
        for (final l in lines.where((l) => (l['qty_remaining'] as num? ?? 0) > 0.001))
          Text(
            '• ${l['description']} — reste dû ${plainNumber(l['qty_remaining'] as num?)}'
            '${(l['missing_value'] as num? ?? 0) > 0 ? ' (${eur(l['missing_value'] as num?)})' : ''}',
            style: const TextStyle(fontSize: 12.5, color: kWarn),
          ),
        for (final l in lines.where(
            (l) => ((l['anomalies'] as List?) ?? const []).isNotEmpty))
          Text(
            '• ${l['description']} — '
            '${((l['anomalies'] as List).cast<String>()).map((a) => _lineAnomalies[a] ?? a).join(' · ')}',
            style: const TextStyle(fontSize: 12.5, color: kMuted),
          ),
      ]),
    );
  }

  Widget _lineCard(BuildContext context, Map<String, dynamic> line) {
    final issues = (line['issues'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final photos = (line['photos'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final productId = line['product_id'] as String?;
    final rejected = line['qty_rejected'] as num? ?? 0;
    final destroyed = line['qty_destroyed'] as num? ?? 0;

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
                            productName: '${line['product_name'] ?? ''}',
                          ),
                        )),
                child: Text('${line['product_name'] ?? line['description'] ?? 'Ligne'}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      decoration: productId == null ? null : TextDecoration.underline,
                    )),
              ),
            ),
            Text('${line['state_label'] ?? ''}',
                style: const TextStyle(fontSize: 11.5, color: kMuted)),
          ]),
          if (line['substituted_product_name'] != null)
            Text('remplacé par ${line['substituted_product_name']}',
                style: const TextStyle(fontSize: 12, color: kWarn)),
          const SizedBox(height: 4),
          Wrap(spacing: 12, children: [
            Text('livré ${plainNumber(line['qty_delivered'] as num?)}',
                style: const TextStyle(fontSize: 12.5)),
            Text('accepté ${plainNumber(line['qty_accepted'] as num?)}',
                style: const TextStyle(
                    fontSize: 12.5, fontWeight: FontWeight.w600, color: kGood)),
            if (rejected > 0)
              Text('refusé ${plainNumber(rejected)}',
                  style: const TextStyle(
                      fontSize: 12.5, fontWeight: FontWeight.w600, color: kBad)),
            if (destroyed > 0)
              Text('détruit ${plainNumber(destroyed)}',
                  style: const TextStyle(
                      fontSize: 12.5, fontWeight: FontWeight.w600, color: kBad)),
          ]),
          for (final i in issues)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '⚠ ${i['qty'] != null ? '${plainNumber(i['qty'] as num?)} × ' : ''}'
                '${i['reason_label'] ?? i['reason']} — ${i['outcome_label'] ?? i['outcome']}',
                style: const TextStyle(fontSize: 12, color: kWarn),
              ),
            ),
          if (photos.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('${photos.length} photo(s)',
                  style: const TextStyle(fontSize: 11.5, color: kMuted)),
            ),
          if (line['notes'] != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('${line['notes']}',
                  style: const TextStyle(fontSize: 12, color: kMuted)),
            ),
        ]),
      ),
    );
  }
}
