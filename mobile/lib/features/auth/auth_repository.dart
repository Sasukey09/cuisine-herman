import 'package:dio/dio.dart';

import '../../core/api_client.dart';

class AuthTokens {
  AuthTokens(this.access, this.refresh);
  final String access;
  final String refresh;
}

class AuthRepository {
  AuthRepository(this._api);
  final ApiClient _api;

  Future<AuthTokens> login(String email, String password) async {
    final resp = await _api.dio.post(
      '/auth/token',
      data: {'username': email, 'password': password},
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    final data = resp.data as Map<String, dynamic>;
    return AuthTokens(
      data['access_token'] as String,
      (data['refresh_token'] as String?) ?? '',
    );
  }

  Future<void> register({
    required String email,
    required String password,
    required String orgName,
    String? name,
  }) async {
    await _api.dio.post('/auth/register', data: {
      'email': email,
      'password': password,
      'org_name': orgName,
      if (name != null && name.isNotEmpty) 'name': name,
    });
  }

  Future<Map<String, dynamic>> me() async {
    final resp = await _api.dio.get('/auth/me');
    return resp.data as Map<String, dynamic>;
  }
}
