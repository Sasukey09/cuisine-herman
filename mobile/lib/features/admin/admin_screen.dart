import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../core/providers.dart';

final _usersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/auth/users');
  return resp.data as List<dynamic>;
});

class AdminScreen extends ConsumerWidget {
  const AdminScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return asyncListView(
      ref: ref,
      provider: _usersProvider,
      empty: 'Aucun utilisateur.',
      itemBuilder: (u) {
        final roles = (u['roles'] as List?)?.join(', ') ?? '';
        return ListTile(
          leading: const Icon(Icons.person_outline),
          title: Text('${u['email'] ?? ''}'),
          subtitle: Text(roles),
        );
      },
    );
  }
}
