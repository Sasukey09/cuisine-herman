import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';

final _marginAlertsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/margin-alerts');
  return resp.data as List<dynamic>;
});

final _topProductsProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/dashboard/top-products', queryParameters: {'limit': 10});
  return resp.data as List<dynamic>;
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alerts = ref.watch(_marginAlertsProvider);
    final top = ref.watch(_topProductsProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(_marginAlertsProvider);
        ref.invalidate(_topProductsProvider);
        await Future.wait([
          ref.read(_marginAlertsProvider.future),
          ref.read(_topProductsProvider.future),
        ]);
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Alertes marges', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          alerts.when(
            loading: () => const _Loading(),
            error: (e, _) => _ErrorText(e),
            data: (rows) => rows.isEmpty
                ? const _Empty('Aucune alerte de marge.')
                : Column(
                    children: rows.map((r) {
                      final m = r as Map<String, dynamic>;
                      return Card(
                        child: ListTile(
                          leading: const Icon(Icons.warning_amber, color: Colors.orange),
                          title: Text('${m['recipe_name'] ?? 'Recette'}'),
                          trailing: Text('${m['food_cost_pct'] ?? '-'} %'),
                        ),
                      );
                    }).toList(),
                  ),
          ),
          const SizedBox(height: 24),
          Text('Top produits', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          top.when(
            loading: () => const _Loading(),
            error: (e, _) => _ErrorText(e),
            data: (rows) => rows.isEmpty
                ? const _Empty('Aucun achat enregistré.')
                : Column(
                    children: rows.map((r) {
                      final m = r as Map<String, dynamic>;
                      return ListTile(
                        dense: true,
                        title: Text('${m['name'] ?? ''}'),
                        trailing: Text('${m['total_spend'] ?? 0} €'),
                      );
                    }).toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) =>
      const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator()));
}

class _ErrorText extends StatelessWidget {
  const _ErrorText(this.error);
  final Object error;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(8),
        child: Text('Erreur de chargement', style: TextStyle(color: Theme.of(context).colorScheme.error)),
      );
}

class _Empty extends StatelessWidget {
  const _Empty(this.text);
  final String text;
  @override
  Widget build(BuildContext context) =>
      Padding(padding: const EdgeInsets.all(8), child: Text(text, style: const TextStyle(color: Colors.grey)));
}
