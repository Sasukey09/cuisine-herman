import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
