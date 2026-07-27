import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kWarn, kGood, kBad, kTerracotta;

/// Supplier detail — the mobile equivalent of the web `/fournisseurs/[id]` page
/// (`frontend/src/features/suppliers/supplier-detail.tsx`): contact details,
/// purchase history and the supplier's price catalogue. None of these endpoints
/// were called by the mobile app before.
final _supplierProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/$id');
  return Map<String, dynamic>.from(resp.data as Map);
});

final _supplierOverviewProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) async {
  final resp = await ref.read(apiClientProvider).dio.get('/suppliers/$id/overview');
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
    final overview = ref.watch(_supplierOverviewProvider(supplierId));
    final history = ref.watch(_supplierHistoryProvider(supplierId));
    final prices = ref.watch(_supplierPricesProvider(supplierId));

    return Scaffold(
      appBar: AppBar(
        title: Text(supplierName, style: const TextStyle(fontFamily: 'Newsreader')),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(_supplierProvider(supplierId));
          ref.invalidate(_supplierOverviewProvider(supplierId));
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
            // --- Fiche 360° ---
            overview.maybeWhen(
              orElse: () => const SizedBox.shrink(),
              data: (o) => _Scorecard(o),
            ),
            const SizedBox(height: 8),
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

/// La fiche fournisseur 360° : volumes, conformité, ponctualité, produits.
///
/// Un score ne s'affiche que s'il a été calculé sur des faits. Sinon « pas
/// encore noté » — jamais un 0 qui accuserait un fournisseur qu'on n'a pas
/// encore éprouvé.
class _Scorecard extends StatelessWidget {
  const _Scorecard(this.o);
  final Map<String, dynamic> o;

  String _pct(dynamic v) => v == null ? '—' : '${(v * 100).round()} %';

  @override
  Widget build(BuildContext context) {
    final score = o['score'] as num?;
    final trend = o['price_trend_pct'] as num?;
    final monthly =
        (o['monthly'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final products =
        (o['top_products'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final scoreColor = score == null
        ? kMuted
        : score >= 80
            ? kGood
            : score >= 50
                ? kWarn
                : kBad;

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: _tile(eur(o['annual_amount'] as num?), 'Payé sur 12 mois', kTerracotta)),
        const SizedBox(width: 8),
        Expanded(
          child: _tile(
            score == null ? '—' : '$score/100',
            score == null ? 'Pas encore noté' : 'Score fournisseur',
            scoreColor,
          ),
        ),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(child: _tile(_pct(o['conformity_rate']),
            'Conformité · ${o['receipt_count']} récept.', kGood)),
        const SizedBox(width: 8),
        Expanded(child: _tile(
            o['on_time_rate'] == null ? '—' : _pct(o['on_time_rate']),
            'Ponctualité${(o['late_count'] as int? ?? 0) > 0 ? ' · ${o['late_count']} retard' : ''}',
            kWarn)),
      ]),
      const SizedBox(height: 8),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Wrap(spacing: 14, runSpacing: 4, children: [
            _count('${o['quote_count']}', 'devis'),
            _count('${o['order_count']}', 'commandes'),
            _count('${o['receipt_count']}', 'réceptions'),
            _count('${o['invoice_count']}', 'factures'),
            _count('${o['distinct_products']}', 'produits'),
            if (trend != null)
              Text(
                '${trend > 0 ? '+' : ''}${trend.toStringAsFixed(1).replaceAll('.', ',')} % prix/an',
                style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: trend > 0 ? kBad : kGood),
              ),
          ]),
        ),
      ),
      if (monthly.length > 1) ...[
        const SizedBox(height: 8),
        _MonthlyBars(monthly),
      ],
      if (products.isNotEmpty) ...[
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Produits les plus achetés',
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: kMuted)),
              const SizedBox(height: 6),
              for (final p in products.take(6))
                Padding(
                  padding: const EdgeInsets.only(bottom: 3),
                  child: Row(children: [
                    Expanded(
                      child: Text('${p['product_name'] ?? 'Produit'}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 13)),
                    ),
                    Text(eur(p['amount'] as num?),
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  ]),
                ),
            ]),
          ),
        ),
      ],
    ]);
  }

  Widget _tile(String value, String label, Color color) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: color)),
            const SizedBox(height: 2),
            Text(label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 11, color: kMuted)),
          ]),
        ),
      );

  Widget _count(String n, String label) => RichText(
        text: TextSpan(children: [
          TextSpan(
              text: '$n ',
              style: const TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF2B2B2B))),
          TextSpan(text: label, style: const TextStyle(fontSize: 13, color: kMuted)),
        ]),
      );
}

class _MonthlyBars extends StatelessWidget {
  const _MonthlyBars(this.monthly);
  final List<Map<String, dynamic>> monthly;

  @override
  Widget build(BuildContext context) {
    final max = monthly
        .map((m) => (m['amount'] as num?)?.toDouble() ?? 0)
        .fold<double>(1, (a, b) => b > a ? b : a);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Dépense mensuelle',
              style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: kMuted)),
          const SizedBox(height: 8),
          SizedBox(
            height: 76,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (final m in monthly)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 2),
                      child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                        Container(
                          height:
                              (((m['amount'] as num?)?.toDouble() ?? 0) / max * 58).clamp(2, 58),
                          decoration: BoxDecoration(
                            color: kTerracotta.withValues(alpha: 0.7),
                            borderRadius:
                                const BorderRadius.vertical(top: Radius.circular(3)),
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text('${m['month']}'.substring(5),
                            style: const TextStyle(fontSize: 8, color: kMuted)),
                      ]),
                    ),
                  ),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}
