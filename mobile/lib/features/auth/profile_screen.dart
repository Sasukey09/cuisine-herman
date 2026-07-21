import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kBad, kTerracotta;
import 'auth_controller.dart';

/// Profile screen — the mobile equivalent of the web `/profile` page
/// (`profile-view.tsx`): identity (name/email/roles/org), logout, and the RGPD
/// actions (data export + organization deletion). The mobile app previously
/// showed only the user's initials, with no way to see or manage the account.
final _meProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final resp = await ref.read(apiClientProvider).dio.get('/auth/me');
  return Map<String, dynamic>.from(resp.data as Map);
});

const _roleLabels = {
  'admin': 'Administrateur',
  'manager': 'Chef de cuisine',
  'viewer': 'Lecture seule',
};

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(_meProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Profil', style: TextStyle(fontFamily: 'Newsreader'))),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(_meProvider);
          await ref.read(_meProvider.future);
        },
        child: me.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(children: [
                const Icon(Icons.cloud_off, size: 32, color: kMuted),
                const SizedBox(height: 10),
                const Text('Impossible de charger le profil',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Text(apiErrorMessage(e),
                    textAlign: TextAlign.center, style: const TextStyle(color: kMuted)),
                const SizedBox(height: 12),
                FilledButton.icon(
                    onPressed: () => ref.invalidate(_meProvider),
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('Réessayer')),
              ]),
            ),
          ]),
          data: (u) {
            final roles = (u['roles'] as List?)?.cast<String>() ?? const [];
            final isAdmin = roles.contains('admin');
            final name = (u['name'] as String?)?.trim();
            final display = (name != null && name.isNotEmpty) ? name : '${u['email'] ?? ''}';
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
              children: [
                Center(
                  child: CircleAvatar(
                    radius: 34,
                    backgroundColor: kTerracotta,
                    child: Text(_initials(display),
                        style: const TextStyle(
                            color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700)),
                  ),
                ),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (name != null && name.isNotEmpty) _kv('Nom', name),
                        _kv('Email', '${u['email'] ?? '—'}'),
                        _kv(
                            'Rôle',
                            roles.isEmpty
                                ? 'Utilisateur'
                                : roles.map((r) => _roleLabels[r] ?? r).join(', ')),
                        _kv('Organisation', '${u['tenant_id'] ?? '—'}'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => ref.read(authControllerProvider.notifier).logout(),
                    icon: const Icon(Icons.logout, size: 18),
                    label: const Text('Déconnexion'),
                  ),
                ),
                if (isAdmin) ...[
                  const SizedBox(height: 24),
                  const Text('Données (RGPD)',
                      style: TextStyle(
                          fontFamily: 'Newsreader', fontSize: 16, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () => _export(context, ref),
                      icon: const Icon(Icons.download_outlined, size: 18),
                      label: const Text('Exporter mes données'),
                    ),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(foregroundColor: kBad),
                      onPressed: () => _deleteOrg(context, ref, '${u['tenant_id'] ?? ''}'),
                      icon: const Icon(Icons.delete_forever_outlined, size: 18),
                      label: const Text("Supprimer l'organisation"),
                    ),
                  ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 110, child: Text(k, style: const TextStyle(color: kMuted))),
            Expanded(child: Text(v, style: const TextStyle(fontWeight: FontWeight.w600))),
          ],
        ),
      );

  String _initials(String s) {
    final t = s.trim();
    if (t.isEmpty) return '?';
    final parts = t.split(RegExp(r'\s+'));
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return t.substring(0, t.length >= 2 ? 2 : 1).toUpperCase();
  }

  /// RGPD art. 15/20 — fetch the full export and copy it to the clipboard (a
  /// phone has no "download folder" the user can reach; clipboard lets them paste
  /// it into an email or a note).
  Future<void> _export(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(content: Text('Export en cours…')));
    try {
      final resp = await ref.read(apiClientProvider).dio.get('/rgpd/export');
      final json = const JsonEncoder.withIndent('  ').convert(resp.data);
      await Clipboard.setData(ClipboardData(text: json));
      messenger.showSnackBar(SnackBar(
          content: Text('Données copiées dans le presse-papier (${json.length} caractères).')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  /// RGPD art. 17 — irreversible. Retype the org name + password, like the web.
  Future<void> _deleteOrg(BuildContext context, WidgetRef ref, String orgId) async {
    final messenger = ScaffoldMessenger.of(context);
    final nameCtrl = TextEditingController();
    final pwdCtrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Supprimer l'organisation ?"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Action IRRÉVERSIBLE : toutes les factures, recettes et prix seront '
              'supprimés. Retapez le nom exact de l\'organisation pour confirmer.',
              style: TextStyle(fontSize: 12.5, color: kMuted),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: nameCtrl,
              decoration: const InputDecoration(labelText: "Nom de l'organisation"),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: pwdCtrl,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Votre mot de passe'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: kBad),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Supprimer définitivement')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(apiClientProvider).dio.post('/rgpd/delete-organization', data: {
        'confirm_name': nameCtrl.text.trim(),
        if (pwdCtrl.text.isNotEmpty) 'password': pwdCtrl.text,
      });
      messenger.showSnackBar(const SnackBar(content: Text('Organisation supprimée.')));
      ref.read(authControllerProvider.notifier).logout();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }
}
