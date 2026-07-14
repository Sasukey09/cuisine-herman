import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
  final _orgName = TextEditingController();
  final _name = TextEditingController();
  bool _registerMode = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _orgName.dispose();
    _name.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final controller = ref.read(authControllerProvider.notifier);
    if (_registerMode) {
      controller.register(
        email: _email.text,
        password: _password.text,
        orgName: _orgName.text,
        name: _name.text,
      );
    } else {
      controller.login(_email.text, _password.text);
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
                    const Icon(Icons.restaurant_menu, size: 48),
                    const SizedBox(height: 8),
                    Text(
                      'FoodGad',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall,
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
                      decoration: const InputDecoration(labelText: 'Email'),
                      validator: (v) =>
                          (v == null || !v.contains('@')) ? 'Email invalide' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _password,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Mot de passe'),
                      validator: (v) =>
                          (v == null || v.isEmpty) ? 'Requis' : null,
                    ),
                    const SizedBox(height: 20),
                    if (state.error != null) ...[
                      Text(
                        state.error!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                      const SizedBox(height: 12),
                    ],
                    FilledButton(
                      onPressed: state.submitting ? null : _submit,
                      child: state.submitting
                          ? const SizedBox(
                              height: 18,
                              width: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(_registerMode ? 'Créer le compte' : 'Se connecter'),
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
