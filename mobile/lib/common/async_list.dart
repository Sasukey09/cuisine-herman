import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../main.dart' show kMuted, kBad;

/// Card-style async list matching the mobile mockup: an always-visible [header]
/// (search pill, drop-zone…) on top, then spaced cards. Pull-to-refresh.
Widget asyncCardList({
  required WidgetRef ref,
  required AutoDisposeFutureProvider<List<dynamic>> provider,
  required Widget Function(Map<String, dynamic> item) itemBuilder,
  String empty = 'Aucun élément.',
  Widget? header,
  EdgeInsets padding = const EdgeInsets.fromLTRB(18, 4, 18, 92),
  double gap = 11,
}) {
  final async = ref.watch(provider);
  return RefreshIndicator(
    onRefresh: () async {
      ref.invalidate(provider);
      await ref.read(provider.future);
    },
    child: ListView(
      padding: padding,
      children: [
        if (header != null) ...[header, SizedBox(height: gap)],
        ...async.when(
          skipLoadingOnReload: true,
          loading: () => const [
            Padding(padding: EdgeInsets.only(top: 40), child: Center(child: CircularProgressIndicator())),
          ],
          error: (e, _) => [
            Padding(
              padding: const EdgeInsets.all(20),
              child: Text('Erreur de chargement.\n$e', style: const TextStyle(color: kBad)),
            ),
          ],
          data: (rows) {
            if (rows.isEmpty) {
              return [
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 28),
                  child: Text(empty, style: const TextStyle(color: kMuted)),
                ),
              ];
            }
            final out = <Widget>[];
            for (var i = 0; i < rows.length; i++) {
              out.add(itemBuilder(rows[i] as Map<String, dynamic>));
              if (i < rows.length - 1) out.add(SizedBox(height: gap));
            }
            return out;
          },
        ),
      ],
    ),
  );
}

/// Renders an async list (loading / error / empty / data) with pull-to-refresh.
/// Cuts the boilerplate for the many read-only list screens.
Widget asyncListView({
  required WidgetRef ref,
  required AutoDisposeFutureProvider<List<dynamic>> provider,
  required Widget Function(Map<String, dynamic> item) itemBuilder,
  String empty = 'Aucun élément.',
}) {
  final async = ref.watch(provider);
  return RefreshIndicator(
    onRefresh: () async {
      ref.invalidate(provider);
      await ref.read(provider.future);
    },
    child: async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ListView(
        children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              'Erreur de chargement.\n${e.toString()}',
              style: const TextStyle(color: Colors.redAccent),
            ),
          ),
        ],
      ),
      data: (rows) {
        if (rows.isEmpty) {
          return ListView(
            children: [
              Padding(
                padding: const EdgeInsets.all(24),
                child: Text(empty, style: const TextStyle(color: Colors.grey)),
              ),
            ],
          );
        }
        return ListView.separated(
          itemCount: rows.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (_, i) => itemBuilder(rows[i] as Map<String, dynamic>),
        );
      },
    ),
  );
}
