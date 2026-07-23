import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/async_list.dart';
import '../../common/format.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kTerracotta;

final _usersProvider = FutureProvider.autoDispose<List<dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/auth/users');
  return resp.data as List<dynamic>;
});

/// Real roles for the org (GET /auth/roles -> ["admin","manager","viewer"]).
/// The invite form now picks from this list instead of a free-text field that
/// let the user type "staff"/"accountant" -> backend 400 "Unknown role".
final _rolesProvider = FutureProvider.autoDispose<List<String>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/auth/roles');
  return (resp.data as List).map((e) => '$e').toList();
});

const _roleLabels = {
  'admin': 'Administrateur',
  'manager': 'Chef de cuisine',
  'viewer': 'Lecture seule',
};

class AdminScreen extends ConsumerWidget {
  const AdminScreen({super.key});

  Future<void> _invite(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final roles = await ref.read(_rolesProvider.future);
    if (!context.mounted) return;
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _InviteDialog(roles: roles),
    );
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

  /// Admin-only: reset a member's password (POST /auth/users/{id}/reset-password).
  /// Mirrors the web reset-password-dialog; the only in-app recovery path when a
  /// mobile user forgets their password.
  Future<void> _resetPassword(BuildContext context, WidgetRef ref, Map user) async {
    final messenger = ScaffoldMessenger.of(context);
    final ctrl = TextEditingController();
    final newPass = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Réinitialiser le mot de passe'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Membre : ${user['email'] ?? ''}',
                style: const TextStyle(fontSize: 12.5, color: kMuted)),
            const SizedBox(height: 8),
            TextField(
              controller: ctrl,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Nouveau mot de passe (min 8)'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text),
              child: const Text('Réinitialiser')),
        ],
      ),
    );
    if (newPass == null || newPass.trim().length < 8) {
      if (newPass != null) {
        messenger.showSnackBar(
            const SnackBar(content: Text('Le mot de passe doit faire au moins 8 caractères.')));
      }
      return;
    }
    try {
      await ref.read(apiClientProvider).dio.post(
          '/auth/users/${user['id']}/reset-password',
          data: {'password': newPass.trim()});
      messenger.showSnackBar(const SnackBar(content: Text('Mot de passe réinitialisé.')));
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
                    IconButton(
                      icon: const Icon(Icons.lock_reset, size: 20, color: kMuted),
                      tooltip: 'Réinitialiser le mot de passe',
                      onPressed: () => _resetPassword(context, ref, u as Map),
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

/// Invite dialog with a REAL role dropdown (fed by GET /auth/roles), so the
/// admin can only pick admin/manager/viewer — no more free-text -> 400.
class _InviteDialog extends StatefulWidget {
  const _InviteDialog({required this.roles});
  final List<String> roles;

  @override
  State<_InviteDialog> createState() => _InviteDialogState();
}

class _InviteDialogState extends State<_InviteDialog> {
  final _email = TextEditingController();
  final _name = TextEditingController();
  final _password = TextEditingController();
  late String _role;

  @override
  void initState() {
    super.initState();
    // Default to the least-privileged role available (viewer if present).
    _role = widget.roles.contains('viewer')
        ? 'viewer'
        : (widget.roles.isNotEmpty ? widget.roles.last : 'viewer');
  }

  @override
  void dispose() {
    _email.dispose();
    _name.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Inviter un utilisateur'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Email'),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Nom (optionnel)'),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Mot de passe (min 8)'),
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: _role,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Rôle'),
              items: [
                for (final r in widget.roles)
                  DropdownMenuItem(value: r, child: Text(_roleLabels[r] ?? r)),
              ],
              onChanged: (v) => setState(() => _role = v ?? _role),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: () {
            if (_email.text.trim().isEmpty || _password.text.trim().isEmpty) return;
            Navigator.pop(context, {
              'email': _email.text.trim(),
              'name': _name.text.trim(),
              'password': _password.text.trim(),
              'role': _role,
            });
          },
          child: const Text('Inviter'),
        ),
      ],
    );
  }
}
