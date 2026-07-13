import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../main.dart' show kMuted;

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
            ErrorState(onRetry: () => ref.invalidate(provider)),
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
          ErrorState(onRetry: () => ref.invalidate(provider)),
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


/// An error the user can act on. The list used to print the raw exception with
/// no way out — the only escape was to kill the app.
class ErrorState extends StatelessWidget {
  const ErrorState({super.key, required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 36, horizontal: 20),
      child: Column(
        children: [
          const Icon(Icons.cloud_off, size: 32, color: kMuted),
          const SizedBox(height: 10),
          const Text(
            'Chargement impossible',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          const Text(
            'Vérifiez votre connexion, puis réessayez.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: kMuted),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Réessayer'),
          ),
        ],
      ),
    );
  }
}
