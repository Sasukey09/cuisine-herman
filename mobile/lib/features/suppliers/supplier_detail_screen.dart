import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kWarn;

/// Supplier detail — the mobile equivalent of the web `/fournisseurs/[id]` page
/// (`frontend/src/features/suppliers/supplier-detail.tsx`): contact details,
/// purchase history and the supplier's price catalogue. None of these endpoints
/// were called by the mobile app before.
final _supplierProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/$id');
  return Map<String, dynamic>.from(resp.data as Map);
});

final _supplierHistoryProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp =
      await ref.read(apiClientProvider).dio.get('/suppliers/$id/purchase-history');
  return Map<String, dynamic>.from(resp.data as Map);
});

final _supplierPricesProvider =
    FutureProvider.autoDispose.family<List<dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/$id/prices');
  return resp.data as List;
});

class SupplierDetailScreen extends ConsumerWidget {
  const SupplierDetailScreen({super.key, required this.supplierId, required this.supplierName});
  final String supplierId;
  final String supplierName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final supplier = ref.watch(_supplierProvider(supplierId));
    final history = ref.watch(_supplierHistoryProvider(supplierId));
    final prices = ref.watch(_supplierPricesProvider(supplierId));

    return Scaffold(
      appBar: AppBar(
        title: Text(supplierName, style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(_supplierProvider(supplierId));
          ref.invalidate(_supplierHistoryProvider(supplierId));
          ref.invalidate(_supplierPricesProvider(supplierId));
          await ref.read(_supplierProvider(supplierId).future);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
          children: [
            // --- Coordonnées ---
            supplier.when(
              loading: () => const _Loading(),
              error: (e, _) => _Line(apiErrorMessage(e)),
              data: (s) {
                final contact = (s['contact'] as Map?) ?? const {};
                final rating = s['rating'] as num?;
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if ((s['code'] ?? '').toString().isNotEmpty)
                          _kv('Code', '${s['code']}'),
                        if ((contact['email'] ?? '').toString().isNotEmpty)
                          _kv('Email', '${contact['email']}'),
                        if ((contact['phone'] ?? '').toString().isNotEmpty)
                          _kv('Téléphone', '${contact['phone']}'),
                        if (rating != null)
                          Row(children: [
                            const SizedBox(width: 90, child: Text('Note', style: TextStyle(color: kMuted))),
                            Text('${rating.toStringAsFixed(1)} ',
                                style: const TextStyle(fontWeight: FontWeight.w600)),
                            const Icon(Icons.star, size: 15, color: kWarn),
                          ]),
                        if ((s['code'] ?? '').toString().isEmpty &&
                            (contact['email'] ?? '').toString().isEmpty &&
                            (contact['phone'] ?? '').toString().isEmpty &&
                            rating == null)
                          const Text('Aucune coordonnée renseignée.',
                              style: TextStyle(color: kMuted)),
                      ],
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 16),
            // --- Historique des achats ---
            const _SectionTitle('Historique des achats'),
            history.when(
              loading: () => const _Loading(),
              error: (e, _) => _Line(apiErrorMessage(e)),
              data: (data) {
                final rows = ((data['purchases'] ?? data['rows']) as List? ?? const [])
                    .map((e) => Map<String, dynamic>.from(e as Map))
                    .toList();
                if (rows.isEmpty) return const _Line('Aucun achat.');
                return Column(
                  children: [
                    for (final p in rows)
                      Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          title: Text(p['product_name'] ?? '—',
                              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                          subtitle: Text(
                            '${p['purchase_date'] ?? ''} · ${_num(p['qty'])} ${p['unit_code'] ?? ''}',
                            style: const TextStyle(fontSize: 12.5, color: kMuted),
                          ),
                          trailing: Text(_money(p['total_price'], p['currency']),
                              style: const TextStyle(fontWeight: FontWeight.w600)),
                        ),
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: 16),
            // --- Catalogue / prix ---
            const _SectionTitle('Catalogue & prix'),
            prices.when(
              loading: () => const _Loading(),
              error: (e, _) => _Line(apiErrorMessage(e)),
              data: (list) {
                if (list.isEmpty) return const _Line('Aucun prix connu.');
                return Column(
                  children: [
                    for (final raw in list)
                      Builder(builder: (_) {
                        final p = Map<String, dynamic>.from(raw as Map);
                        return Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            dense: true,
                            title: Text(p['product_name'] ?? '—',
                                style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
                            subtitle: (p['effective_date'] != null)
                                ? Text('${p['effective_date']}',
                                    style: const TextStyle(fontSize: 12, color: kMuted))
                                : null,
                            trailing: Text(_money(p['price'], p['currency']),
                                style: const TextStyle(fontWeight: FontWeight.w600)),
                          ),
                        );
                      }),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 90, child: Text(k, style: const TextStyle(color: kMuted))),
            Expanded(child: Text(v, style: const TextStyle(fontWeight: FontWeight.w600))),
          ],
        ),
      );
}

String _num(dynamic v) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse('$v');
  if (n == null) return '$v';
  return n == n.roundToDouble() ? '${n.toInt()}' : n.toString().replaceAll('.', ',');
}

String _money(dynamic total, dynamic currency) {
  final t = total is num ? total : num.tryParse('${total ?? ''}');
  if (t == null) return '—';
  if (currency == null || currency == 'EUR' || currency == '€') return eur(t);
  return '${t.toStringAsFixed(2).replaceAll('.', ',')} $currency';
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 4, 4, 8),
        child: Text(text,
            style: const TextStyle(
                fontFamily: 'Newsreader', fontSize: 17, fontWeight: FontWeight.w700)),
      );
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 20),
        child: Center(child: CircularProgressIndicator()),
      );
}

class _Line extends StatelessWidget {
  const _Line(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Center(child: Text(text, style: const TextStyle(color: kMuted))),
      );
}
