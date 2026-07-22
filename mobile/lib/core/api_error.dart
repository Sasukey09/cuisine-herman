import 'package:dio/dio.dart';

/// Human-readable message from a FastAPI error response (mirrors the web util).
String apiErrorMessage(Object error, [String fallback = 'Une erreur est survenue']) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map && data['detail'] is String) {
      return data['detail'] as String;
    }
    if (data is Map && data['detail'] is List) {
      final list = data['detail'] as List;
      final msgs = list
          .whereType<Map>()
          .map((e) => e['msg'])
          .whereType<String>()
          .toList();
      if (msgs.isNotEmpty) return msgs.join(', ');
    }
    // A slow/unreachable server (typically a free-tier cold start) is NOT a
    // client mistake. It must never fall through to a caller fallback like
    // "Identifiants incorrects" — that sends the user resetting a password that
    // was never wrong. receiveTimeout/sendTimeout are the cold-start symptom the
    // old code missed (it only caught the two connection-* types).
    switch (error.type) {
      case DioExceptionType.connectionError:
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.sendTimeout:
        return 'Serveur injoignable (il démarre peut-être). Réessayez dans un instant.';
      default:
        break;
    }
    // A 5xx (incl. the 502/503 a waking server returns) is a server problem, not
    // bad credentials — again, don't leak the caller's fallback.
    final status = error.response?.statusCode ?? 0;
    if (status >= 500) {
      return 'Serveur momentanément indisponible. Réessayez dans un instant.';
    }
  }
  return fallback;
}
