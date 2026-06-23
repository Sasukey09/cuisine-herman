import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/create_dialog.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kTerracotta, kGood;

final _usersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/auth/users');
  return resp.data as List<dynamic>;
});

const _roleLabels = {
  'admin': 'Administrateur',
  'manager': 'Chef de cuisine',
  'staff': 'Commis',
  'accountant': 'Comptable',
  'viewer': 'Lecture seule',
};

class AdminScreen extends ConsumerWidget {
  const AdminScreen({super.key});

  Future<void> _invite(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final data = await showCreateDialog(context, title: 'Inviter un utilisateur', fields: const [
      CreateField('email', 'Email', required: true),
      CreateField('name', 'Nom (optionnel)'),
      CreateField('password', 'Mot de passe', required: true),
      CreateField('role', 'Rôle (admin, manager, staff…)', required: true),
    ]);
    if (data == null) return;
    try {
      await ref.read(apiClientProvider).dio.post('/auth/users', data: {
        'email': data['email'],
        'password': data['password'],
        if ((data['name'] ?? '').isNotEmpty) 'name': data['name'],
        'role': data['role'],
      });
      ref.invalidate(_usersProvider);
      messenger.showSnackBar(const SnackBar(content: Text('Utilisateur invité.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(
      children: [
        Expanded(
          child: asyncCardList(
            ref: ref,
            provider: _usersProvider,
            empty: 'Aucun utilisateur.',
            itemBuilder: (u) {
              final name = '${u['name'] ?? ''}'.trim();
              final email = '${u['email'] ?? ''}';
              final display = name.isNotEmpty ? name : email;
              final initials = _initials(display);
              final roles = (u['roles'] as List?)?.cast<String>() ?? const [];
              final roleLabel = roles.isEmpty
                  ? 'Utilisateur'
                  : roles.map((r) => _roleLabels[r] ?? r).join(', ');
              return MockCard(
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 18,
                      backgroundColor: const Color(0xFFEFE1D3),
                      child: Text(initials,
                          style: const TextStyle(
                              color: kTerracotta, fontSize: 12, fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(display,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 2),
                          Text(roleLabel,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 12, color: kMuted)),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE3ECDB),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: const Text('Actif',
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: kGood)),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 4, 18, 12),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => _invite(context, ref),
                child: const Text('+ Inviter un utilisateur'),
              ),
            ),
          ),
        ),
      ],
    );
  }

  String _initials(String s) {
    final t = s.trim();
    if (t.isEmpty) return '?';
    final parts = t.split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return t.substring(0, t.length >= 2 ? 2 : 1).toUpperCase();
  }
}
