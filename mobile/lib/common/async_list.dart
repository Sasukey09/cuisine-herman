import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/offline_cache.dart';
import '../core/outbox.dart';
import '../core/providers.dart';
import '../main.dart' show kMuted, kWarn;

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


/// Says out loud that what is on screen is not live.
///
/// The alternative — silently showing yesterday's costs — is how a chef prices a
/// dish on a price that changed this morning.
class StaleBanner extends StatelessWidget {
  const StaleBanner({super.key, required this.age});
  final Duration age;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 11),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: const Color(0xFFF6EAD4),
        borderRadius: BorderRadius.circular(11),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_off, size: 16, color: kWarn),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Hors connexion — données de ${formatAge(age)}',
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF8A5A22)),
            ),
          ),
        ],
      ),
    );
  }
}

/// Offline-first list: the same card layout, but backed by the cache when the
/// network is gone, and honest about it.
Widget offlineCardList({
  required WidgetRef ref,
  required AutoDisposeFutureProvider<Loaded> provider,
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
            Padding(
              padding: EdgeInsets.only(top: 40),
              child: Center(child: CircularProgressIndicator()),
            ),
          ],
          error: (e, _) => [ErrorState(onRetry: () => ref.invalidate(provider))],
          data: (loaded) {
            final rows = (loaded.data as List?) ?? const [];
            final out = <Widget>[];
            if (loaded.isStale && loaded.age != null) {
              out.add(StaleBanner(age: loaded.age!));
            }
            if (rows.isEmpty) {
              out.add(Padding(
                padding: const EdgeInsets.symmetric(vertical: 28),
                child: Text(empty, style: const TextStyle(color: kMuted)),
              ));
              return out;
            }
            for (var i = 0; i < rows.length; i++) {
              out.add(itemBuilder((rows[i] as Map).cast<String, dynamic>()));
              if (i < rows.length - 1) out.add(SizedBox(height: gap));
            }
            return out;
          },
        ),
      ],
    ),
  );
}

/// Shows what is waiting to be sent. A queue the user cannot see is a queue they
/// cannot trust — they would re-create the product "just in case", and end up
/// with two.
class PendingWritesBanner extends ConsumerWidget {
  const PendingWritesBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final outbox = ref.watch(outboxProvider);
    final pending = outbox.maybeWhen(data: (o) => o.list(), orElse: () => const <PendingWrite>[]);
    if (pending.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.only(bottom: 11),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFE9E2D2),
        borderRadius: BorderRadius.circular(11),
      ),
      child: Row(
        children: [
          const Icon(Icons.schedule_send, size: 16, color: Color(0xFF8A7F70)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${pending.length} création(s) en attente d\'envoi : '
              '${pending.map((p) => p.label).take(2).join(', ')}'
              '${pending.length > 2 ? '…' : ''}',
              style: const TextStyle(fontSize: 12.5, color: Color(0xFF6B6357)),
            ),
          ),
        ],
      ),
    );
  }
}
