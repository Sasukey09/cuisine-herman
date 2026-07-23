import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kGradBrand, kGlow, kSerif;
import 'auth_controller.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _orgName = TextEditingController();
  final _name = TextEditingController();
  bool _registerMode = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _confirm.dispose();
    _orgName.dispose();
    _name.dispose();
    super.dispose();
  }

  /// Self-service recovery — step 1 (POST /auth/forgot-password). The server
  /// always answers the same way (anti-enumeration); the reset link arrives by
  /// email and opens the web reset page. Before this, mobile had no way out.
  Future<void> _forgotPassword() async {
    final messenger = ScaffoldMessenger.of(context);
    final ctrl = TextEditingController(text: _email.text.trim());
    final email = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Mot de passe oublié'),
        content: TextField(
          controller: ctrl,
          keyboardType: TextInputType.emailAddress,
          autocorrect: false,
          decoration: const InputDecoration(labelText: 'Votre email'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim().toLowerCase()),
              child: const Text('Envoyer le lien')),
        ],
      ),
    );
    if (email == null || !email.contains('@')) return;
    try {
      await ref.read(apiClientProvider).dio.post('/auth/forgot-password', data: {'email': email});
    } catch (e) {
      // A failure must not reveal whether the address exists; show the same
      // generic message unless it's clearly a network problem.
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
      return;
    }
    messenger.showSnackBar(const SnackBar(
      content: Text('Si un compte existe, un email de réinitialisation a été envoyé.'),
    ));
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final controller = ref.read(authControllerProvider.notifier);
    // Normaliser comme le backend (strip + lowercase) : sinon un email tape avec
    // une majuscule (auto-capitalisation iOS) ne matche pas le compte stocke en
    // minuscules et la connexion echoue.
    final email = _email.text.trim().toLowerCase();
    if (_registerMode) {
      controller.register(
        email: email,
        password: _password.text,
        orgName: _orgName.text,
        name: _name.text,
      );
    } else {
      controller.login(email, _password.text);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authControllerProvider);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: Container(
                        width: 56,
                        height: 56,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          gradient: kGradBrand,
                          borderRadius: BorderRadius.circular(14),
                          boxShadow: kGlow,
                        ),
                        child: const Text('F',
                            style: TextStyle(
                                fontFamily: 'Newsreader',
                                fontSize: 30,
                                fontWeight: FontWeight.w700,
                                color: Colors.white)),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'FoodGad',
                      textAlign: TextAlign.center,
                      style: kSerif.copyWith(
                          fontSize: 26, color: Theme.of(context).colorScheme.onSurface),
                    ),
                    const SizedBox(height: 24),
                    if (_registerMode) ...[
                      TextFormField(
                        controller: _orgName,
                        decoration: const InputDecoration(labelText: 'Nom du restaurant'),
                        validator: (v) =>
                            (v == null || v.trim().isEmpty) ? 'Requis' : null,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _name,
                        decoration: const InputDecoration(labelText: 'Votre nom (optionnel)'),
                      ),
                      const SizedBox(height: 12),
                    ],
                    TextFormField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                      textCapitalization: TextCapitalization.none,
                      decoration: const InputDecoration(labelText: 'Email'),
                      validator: (v) =>
                          (v == null || !v.contains('@')) ? 'Email invalide' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _password,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Mot de passe'),
                      validator: (v) {
                        if (v == null || v.isEmpty) return 'Requis';
                        // À l'inscription, imposer la même règle que le backend
                        // (min 8) — sinon compte trop faible et, sans reset in-app,
                        // une faute de frappe = compte inaccessible.
                        if (_registerMode && v.length < 8) {
                          return '8 caractères minimum';
                        }
                        return null;
                      },
                    ),
                    if (_registerMode) ...[
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _confirm,
                        obscureText: true,
                        decoration:
                            const InputDecoration(labelText: 'Confirmer le mot de passe'),
                        validator: (v) =>
                            (v != _password.text) ? 'Les mots de passe ne correspondent pas' : null,
                      ),
                    ],
                    if (!_registerMode)
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                          onPressed: state.submitting ? null : _forgotPassword,
                          child: const Text('Mot de passe oublié ?'),
                        ),
                      ),
                    const SizedBox(height: 20),
                    if (state.error != null) ...[
                      Text(
                        state.error!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                      const SizedBox(height: 12),
                    ],
                    GradientButton(
                      label: _registerMode ? 'Créer le compte' : 'Se connecter',
                      onPressed: state.submitting ? null : _submit,
                      expand: true,
                      loading: state.submitting,
                    ),
                    TextButton(
                      onPressed: state.submitting
                          ? null
                          : () => setState(() => _registerMode = !_registerMode),
                      child: Text(_registerMode
                          ? 'J\'ai déjà un compte'
                          : 'Créer une organisation'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
