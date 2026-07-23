import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn, kBad, kTerracotta;
import '../orders/orders_screen.dart' show ordersListProvider;
import 'receipt_detail_screen.dart';
import 'receipts_screen.dart' show receiptsListProvider, qualityVocabularyProvider;

/// Le brouillon proposé pour une commande : ce qui RESTE dû.
final receiptPrefillProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, orderId) async {
  final resp =
      await ref.read(apiClientProvider).dio.get('/receipts/from-order/$orderId');
  return Map<String, dynamic>.from(resp.data as Map);
});

/// Une anomalie en cours de saisie.
class IssueDraft {
  IssueDraft({this.qty, this.reason = 'product_damaged', this.outcome = 'rejected'});
  num? qty;
  String reason;
  String outcome;

  Map<String, dynamic> toJson() =>
      {'qty': qty, 'reason': reason, 'outcome': outcome};
}

/// Une ligne en cours de réception.
class ReceptionLineDraft {
  ReceptionLineDraft({
    required this.orderLineId,
    required this.productId,
    required this.description,
    this.qtyOrdered,
    this.qtyAlreadyReceived = 0,
    this.qtyDelivered,
    this.unitId,
    this.unitPrice,
    this.packSize,
  });

  final String? orderLineId;
  final String? productId;
  final String? description;
  final num? qtyOrdered;
  final num qtyAlreadyReceived;
  num? qtyDelivered;
  final int? unitId;
  final num? unitPrice;
  final String? packSize;
  final List<IssueDraft> issues = [];
  final List<String> photos = [];
  String? notes;

  /// La même règle que le serveur, recalculée ici pour que le réceptionnaire
  /// voie l'effet de sa saisie sans aller-retour. Le serveur reste la référence.
  ({num delivered, num accepted, num rejected, num destroyed, String state}) get totals {
    final delivered = qtyDelivered ?? 0;
    num rejected = 0, destroyed = 0, flagged = 0;
    for (final i in issues) {
      // Anomalie sans quantité : elle porte sur toute la ligne.
      final q = i.qty ?? delivered;
      flagged += q;
      if (i.outcome == 'rejected') rejected += q;
      if (i.outcome == 'destroyed') destroyed += q;
    }
    final lost = (rejected + destroyed) > delivered ? delivered : (rejected + destroyed);
    final accepted = delivered - lost < 0 ? 0 : delivered - lost;
    final state = delivered <= 0
        ? 'En attente'
        : accepted <= 0
            ? 'Refusée'
            : flagged > 0
                ? 'Partiellement conforme'
                : 'Conforme';
    return (
      delivered: delivered,
      accepted: accepted,
      rejected: rejected > delivered ? delivered : rejected,
      destroyed: destroyed,
      state: state,
    );
  }

  Map<String, dynamic> toJson() => {
        'order_line_id': orderLineId,
        'product_id': productId,
        'description': description,
        'qty_delivered': qtyDelivered,
        'unit_id': unitId,
        'unit_price': unitPrice,
        'pack_size': packSize,
        'notes': (notes ?? '').trim().isEmpty ? null : notes!.trim(),
        'issues': issues.map((i) => i.toJson()).toList(),
        'photos': photos.map((u) => {'url': u}).toList(),
      };
}

Color stateColor(String state) {
  switch (state) {
    case 'Conforme':
      return kGood;
    case 'Partiellement conforme':
      return kWarn;
    case 'Refusée':
      return kBad;
    case 'Remplacée':
      return kTerracotta;
    default:
      return kMuted;
  }
}

/// Le poste de réception d'une commande — pendant mobile de l'écran web.
///
/// Un réceptionnaire ne valide pas des quantités : il contrôle une livraison.
/// L'écran est donc construit autour de la ligne — ce qui est arrivé, ce qu'on
/// en accepte, et pourquoi.
class ReceptionStationScreen extends ConsumerStatefulWidget {
  const ReceptionStationScreen({super.key, required this.orderId, this.orderReference});
  final String orderId;
  final String? orderReference;

  @override
  ConsumerState<ReceptionStationScreen> createState() => _State();
}

class _State extends ConsumerState<ReceptionStationScreen> {
  final _deliveryNote = TextEditingController();
  final _notes = TextEditingController();
  List<ReceptionLineDraft>? _lines;
  String? _supplierId;
  bool _saving = false;

  @override
  void dispose() {
    _deliveryNote.dispose();
    _notes.dispose();
    super.dispose();
  }

  void _hydrate(Map<String, dynamic> prefill) {
    if (_lines != null) return;
    _supplierId = prefill['supplier_id'] as String?;
    _lines = ((prefill['lines'] as List?) ?? const [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .map((l) => ReceptionLineDraft(
              orderLineId: l['order_line_id'] as String?,
              productId: l['product_id'] as String?,
              description: l['description'] as String?,
              qtyOrdered: l['qty_ordered'] as num?,
              qtyAlreadyReceived: (l['qty_already_received'] as num?) ?? 0,
              // Pré-rempli avec ce qui RESTE dû : proposer la quantité
              // commandée re-proposerait du déjà reçu dès la 2e livraison.
              qtyDelivered: l['qty_delivered'] as num?,
              unitId: l['unit_id'] as int?,
              unitPrice: l['unit_price'] as num?,
              packSize: l['pack_size'] as String?,
            ))
        .toList();
  }

  Future<void> _save({required bool thenValidate}) async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    setState(() => _saving = true);
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.post('/receipts/', data: {
        'order_id': widget.orderId,
        'supplier_id': _supplierId,
        'received_at': DateTime.now().toIso8601String().substring(0, 10),
        'delivery_note_number':
            _deliveryNote.text.trim().isEmpty ? null : _deliveryNote.text.trim(),
        'notes': _notes.text.trim().isEmpty ? null : _notes.text.trim(),
        // L'appareil de saisie : un téléphone en chambre froide et un poste en
        // bureau n'expliquent pas de la même façon une saisie douteuse.
        'device_info': 'Android',
        'lines': _lines!.map((l) => l.toJson()).toList(),
      });
      final receipt = Map<String, dynamic>.from(resp.data as Map);

      Map<String, dynamic>? control;
      if (thenValidate) {
        final v = await dio.post('/receipts/${receipt['id']}/validate');
        control = Map<String, dynamic>.from(
            (v.data as Map)['control'] as Map);
      }
      ref.invalidate(receiptsListProvider(null));
      ref.invalidate(ordersListProvider(null));

      if (control != null) {
        final issues = control['issue_count'] as int? ?? 0;
        messenger.showSnackBar(SnackBar(
          content: Text(issues == 0
              ? 'Réception conforme et validée'
              : 'Réception validée · $issues anomalie(s)'
                  '${(control['missing_value'] as num? ?? 0) > 0 ? ' · ${eur(control['missing_value'] as num?)} manquants' : ''}'),
        ));
      }
      navigator.pushReplacement(MaterialPageRoute(
        builder: (_) => ReceiptDetailScreen(
          receiptId: '${receipt['id']}',
          reference: receipt['reference'] as String?,
        ),
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final prefill = ref.watch(receiptPrefillProvider(widget.orderId));
    final vocabulary = ref.watch(qualityVocabularyProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Réception', style: TextStyle(fontFamily: 'Newsreader')),
      ),
      body: prefill.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text(apiErrorMessage(e))),
        data: (data) {
          _hydrate(data);
          final lines = _lines ?? const <ReceptionLineDraft>[];
          if (lines.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text("Cette commande n'a plus rien à recevoir.",
                    textAlign: TextAlign.center, style: TextStyle(color: kMuted)),
              ),
            );
          }
          final accepted =
              lines.fold<num>(0, (s, l) => s + l.totals.accepted);
          final anomalies = lines.fold<int>(0, (s, l) => s + l.issues.length);

          return Column(children: [
            Expanded(
              child: ListView(padding: const EdgeInsets.all(14), children: [
                MockCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Commande ${data['order_reference'] ?? ''}',
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _deliveryNote,
                      decoration: const InputDecoration(labelText: 'N° de bon de livraison'),
                    ),
                    TextField(
                      controller: _notes,
                      decoration: const InputDecoration(labelText: 'Observations'),
                    ),
                  ]),
                ),
                const SizedBox(height: 10),
                for (var i = 0; i < lines.length; i++)
                  _lineCard(lines[i], vocabulary.value),
              ]),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 4, 14, 10),
                child: Column(children: [
                  Row(children: [
                    Text('${_n(accepted)} accepté(s)',
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    if (anomalies > 0) ...[
                      const SizedBox(width: 8),
                      Text('$anomalies anomalie(s)',
                          style: const TextStyle(fontSize: 12.5, color: kWarn)),
                    ],
                  ]),
                  const SizedBox(height: 6),
                  Row(children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _saving ? null : () => _save(thenValidate: false),
                        child: const Text('Brouillon'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      flex: 2,
                      child: GradientButton(
                        label: 'Valider la réception',
                        onPressed: _saving ? null : () => _save(thenValidate: true),
                        expand: true,
                        loading: _saving,
                      ),
                    ),
                  ]),
                  const SizedBox(height: 4),
                  const Text(
                    'Une réception validée ne se modifie plus.',
                    style: TextStyle(fontSize: 11, color: kMuted),
                  ),
                ]),
              ),
            ),
          ]);
        },
      ),
    );
  }

  Widget _lineCard(ReceptionLineDraft line, Map<String, dynamic>? vocabulary) {
    final t = line.totals;
    final remaining = (line.qtyOrdered ?? 0) - line.qtyAlreadyReceived - t.accepted;
    final reasons =
        ((vocabulary?['reasons'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final outcomes =
        ((vocabulary?['outcomes'] as List?) ?? const []).cast<Map<String, dynamic>>();

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: MockCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(line.description ?? 'Ligne',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: stateColor(t.state).withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(t.state,
                  style: TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w600, color: stateColor(t.state))),
            ),
          ]),
          Text(
            [
              if (line.qtyOrdered != null) 'commandé ${_n(line.qtyOrdered!)}',
              if (line.qtyAlreadyReceived > 0) 'déjà reçu ${_n(line.qtyAlreadyReceived)}',
              if (line.packSize != null) '${line.packSize}',
            ].join('  ·  '),
            style: const TextStyle(fontSize: 12, color: kMuted),
          ),
          const SizedBox(height: 8),
          Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            SizedBox(
              width: 92,
              child: TextFormField(
                initialValue: plainNumber(line.qtyDelivered),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(isDense: true, labelText: 'Livré'),
                onChanged: (v) => setState(() => line.qtyDelivered =
                    v.trim().isEmpty ? null : num.tryParse(v.replaceAll(',', '.'))),
              ),
            ),
            const SizedBox(width: 10),
            // Accepté / refusé / détruit ne se saisissent pas : ils se
            // déduisent des anomalies. Les afficher évite de faire recompter.
            Expanded(
              child: Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Wrap(spacing: 10, children: [
                  Text('accepté ${_n(t.accepted)}',
                      style: const TextStyle(
                          fontSize: 12.5, fontWeight: FontWeight.w600, color: kGood)),
                  if (t.rejected > 0)
                    Text('refusé ${_n(t.rejected)}',
                        style: const TextStyle(
                            fontSize: 12.5, fontWeight: FontWeight.w600, color: kBad)),
                  if (t.destroyed > 0)
                    Text('détruit ${_n(t.destroyed)}',
                        style: const TextStyle(
                            fontSize: 12.5, fontWeight: FontWeight.w600, color: kBad)),
                  if (remaining > 0.001)
                    Text('reste dû ${_n(remaining)}',
                        style: const TextStyle(fontSize: 12.5, color: kWarn)),
                ]),
              ),
            ),
          ]),
          for (var i = 0; i < line.issues.length; i++)
            _issueRow(line, i, reasons, outcomes),
          const SizedBox(height: 4),
          Row(children: [
            TextButton.icon(
              onPressed: () => setState(() => line.issues.add(IssueDraft())),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Anomalie', style: TextStyle(fontSize: 12.5)),
            ),
            TextButton.icon(
              onPressed: () => _addPhoto(line),
              icon: const Icon(Icons.photo_camera_outlined, size: 16),
              label: Text(
                  line.photos.isEmpty ? 'Photo' : 'Photos (${line.photos.length})',
                  style: const TextStyle(fontSize: 12.5)),
            ),
          ]),
        ]),
      ),
    );
  }

  Widget _issueRow(ReceptionLineDraft line, int index, List<Map<String, dynamic>> reasons,
      List<Map<String, dynamic>> outcomes) {
    final issue = line.issues[index];
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.fromLTRB(8, 4, 4, 4),
      decoration: BoxDecoration(
        color: const Color(0xFFF6EAD4).withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(children: [
        Row(children: [
          SizedBox(
            width: 68,
            child: TextFormField(
              initialValue: plainNumber(issue.qty),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                  isDense: true, labelText: 'Qté', hintText: 'tout'),
              onChanged: (v) => setState(() => issue.qty =
                  v.trim().isEmpty ? null : num.tryParse(v.replaceAll(',', '.'))),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: DropdownButtonFormField<String>(
              initialValue: issue.reason,
              isDense: true,
              isExpanded: true,
              decoration: const InputDecoration(isDense: true),
              items: [
                for (final r in reasons)
                  DropdownMenuItem(
                      value: '${r['value']}',
                      child: Text('${r['label']}',
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12.5))),
              ],
              onChanged: (v) => setState(() => issue.reason = v ?? issue.reason),
            ),
          ),
          IconButton(
            onPressed: () => setState(() => line.issues.removeAt(index)),
            icon: const Icon(Icons.close, size: 18),
            visualDensity: VisualDensity.compact,
          ),
        ]),
        DropdownButtonFormField<String>(
          initialValue: issue.outcome,
          isDense: true,
          isExpanded: true,
          decoration: const InputDecoration(isDense: true, labelText: 'Décision'),
          items: [
            for (final o in outcomes)
              DropdownMenuItem(
                  value: '${o['value']}',
                  child: Text('${o['label']}', style: const TextStyle(fontSize: 12.5))),
          ],
          onChanged: (v) => setState(() => issue.outcome = v ?? issue.outcome),
        ),
      ]),
    );
  }

  Future<void> _addPhoto(ReceptionLineDraft line) async {
    final controller = TextEditingController();
    final url = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Photo de la ligne'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Adresse de la photo'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Annuler')),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(controller.text.trim()),
            child: const Text('Ajouter'),
          ),
        ],
      ),
    );
    if (url != null && url.isNotEmpty) setState(() => line.photos.add(url));
  }

  String _n(num v) => plainNumber(v);
}
