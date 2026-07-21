import 'package:dio/dio.dart';

import 'config.dart';
import 'token_store.dart';

/// Dio wrapper that attaches the bearer token on every request and transparently
/// refreshes it once on a 401 (mirrors the web app's axios interceptor).
class ApiClient {
  ApiClient(this.tokenStore)
      : dio = Dio(BaseOptions(
          baseUrl: AppConfig.apiBaseUrl,
          // Without timeouts a request that connects but never answers (Render
          // free-tier cold start, a stalled proxy, a half-open connection) never
          // returns AND never throws — so the launch `me()` call in
          // auth_controller._bootstrap hangs and the app sits on a full-screen
          // spinner forever. Finite timeouts turn that into a thrown error, which
          // _bootstrap already handles by dropping cleanly to the login screen.
          // 60s of receive budget survives a typical cold start; heavy uploads
          // (invoice OCR) still override this per request.
          connectTimeout: const Duration(seconds: 20),
          receiveTimeout: const Duration(seconds: 60),
        )) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await tokenStore.accessToken;
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          // Don't try to refresh on the token/refresh calls themselves.
          final path = error.requestOptions.path;
          final isTokenCall = path.endsWith('/auth/token') || path.endsWith('/auth/refresh');
          final alreadyRetried = error.requestOptions.extra['retried'] == true;
          if (error.response?.statusCode == 401 && !isTokenCall && !alreadyRetried) {
            final refreshed = await _refresh();
            if (refreshed) {
              final opts = error.requestOptions;
              opts.extra['retried'] = true;
              final token = await tokenStore.accessToken;
              opts.headers['Authorization'] = 'Bearer $token';
              try {
                final response = await dio.fetch(opts);
                return handler.resolve(response);
              } catch (_) {
                // fall through to logout
              }
            }
            onUnauthorized?.call();
          }
          handler.next(error);
        },
      ),
    );
  }

  final Dio dio;
  final TokenStore tokenStore;

  /// Called when refresh fails — the app should route back to login.
  void Function()? onUnauthorized;

  Future<bool> _refresh() async {
    final refresh = await tokenStore.refreshToken;
    if (refresh == null) return false;
    try {
      // bare Dio so the interceptor doesn't recurse (same finite timeouts, so a
      // stalled refresh can't hang the retry either)
      final resp = await Dio(BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: const Duration(seconds: 20),
        receiveTimeout: const Duration(seconds: 60),
      )).post('/auth/refresh', data: {'refresh_token': refresh});
      final data = resp.data as Map<String, dynamic>;
      await tokenStore.save(
        data['access_token'] as String,
        (data['refresh_token'] as String?) ?? refresh,
      );
      return true;
    } catch (_) {
      return false;
    }
  }
}
