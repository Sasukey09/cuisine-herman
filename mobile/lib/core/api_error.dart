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
    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout) {
      return 'Impossible de joindre le serveur.';
    }
  }
  return fallback;
}
