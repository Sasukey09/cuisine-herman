import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_error.dart';
import '../../core/providers.dart';
import 'auth_repository.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthState {
  const AuthState({
    this.status = AuthStatus.unknown,
    this.user,
    this.submitting = false,
    this.error,
  });

  final AuthStatus status;
  final Map<String, dynamic>? user;
  final bool submitting;
  final String? error;

  AuthState copyWith({
    AuthStatus? status,
    Map<String, dynamic>? user,
    bool? submitting,
    String? error,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
      submitting: submitting ?? this.submitting,
      error: error,
    );
  }
}

class AuthController extends Notifier<AuthState> {
  late final AuthRepository _repo;

  @override
  AuthState build() {
    final api = ref.read(apiClientProvider);
    _repo = AuthRepository(api);
    // When a refresh ultimately fails, drop to the login screen.
    api.onUnauthorized = () {
      state = const AuthState(status: AuthStatus.unauthenticated);
    };
    _bootstrap();
    return const AuthState();
  }

  Future<void> _bootstrap() async {
    final token = await ref.read(tokenStoreProvider).accessToken;
    if (token == null) {
      state = const AuthState(status: AuthStatus.unauthenticated);
      return;
    }
    try {
      final me = await _repo.me();
      state = AuthState(status: AuthStatus.authenticated, user: me);
    } catch (_) {
      state = const AuthState(status: AuthStatus.unauthenticated);
    }
  }

  Future<void> login(String email, String password) async {
    state = state.copyWith(submitting: true, error: null);
    try {
      final tokens = await _repo.login(email.trim(), password);
      await ref.read(tokenStoreProvider).save(tokens.access, tokens.refresh);
      final me = await _repo.me();
      state = AuthState(status: AuthStatus.authenticated, user: me);
    } catch (e) {
      state = state.copyWith(
        submitting: false,
        error: apiErrorMessage(e, 'Identifiants incorrects'),
      );
    }
  }

  Future<void> register({
    required String email,
    required String password,
    required String orgName,
    String? name,
  }) async {
    state = state.copyWith(submitting: true, error: null);
    try {
      await _repo.register(
        email: email.trim(),
        password: password,
        orgName: orgName.trim(),
        name: name,
      );
      await login(email, password); // auto-login after registration
    } catch (e) {
      state = state.copyWith(submitting: false, error: apiErrorMessage(e));
    }
  }

  Future<void> logout() async {
    // Revoke the tokens server-side (every device). Clearing local storage
    // alone left a stolen refresh token valid for its full 14-day life.
    // Best-effort: a network failure must never trap the user in the app.
    try {
      await ref.read(apiClientProvider).dio.post('/auth/logout');
    } catch (_) {
      // offline, or the token is already dead — log out locally anyway
    }
    await ref.read(tokenStoreProvider).clear();
    // Wipe this account's local data so the next user on the same device never
    // sees it: the offline cache (cached products/invoices/recipes/suppliers)
    // and the outbox (pending offline writes, which would otherwise replay into
    // the next user's tenant). Best-effort: a failure here must not trap logout.
    try {
      await (await ref.read(offlineCacheProvider.future)).clear();
      await (await ref.read(outboxProvider.future)).clear();
    } catch (_) {
      // storage unavailable — token is already gone, which is the essential part
    }
    state = const AuthState(status: AuthStatus.unauthenticated);
  }
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);

/// Write access = admin or manager, like the web `hasRole("admin","manager")`.
/// A viewer gets read-only screens (no create/edit/delete affordances); the
/// backend enforces the same via `require_writer`, so this is purely UX — it
/// stops showing buttons that would only 403.
final canWriteProvider = Provider<bool>((ref) {
  final roles =
      (ref.watch(authControllerProvider).user?['roles'] as List?)?.cast<String>() ?? const [];
  return roles.contains('admin') || roles.contains('manager');
});
