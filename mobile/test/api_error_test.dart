import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:foodgad_mobile/core/api_error.dart';

void main() {
  final req = RequestOptions(path: '/auth/token');

  DioException withType(DioExceptionType type) =>
      DioException(requestOptions: req, type: type);

  DioException withStatus(int code, [Object? body]) => DioException(
        requestOptions: req,
        type: DioExceptionType.badResponse,
        response: Response(requestOptions: req, statusCode: code, data: body),
      );

  group('apiErrorMessage — the login screen must never lie about credentials', () {
    // The bug: on a Render free-tier cold start the /auth/token call times out or
    // gets a 502/503. The old util only handled connection*-timeouts, so every
    // other failure fell through to the caller's fallback — for login that is
    // "Identifiants incorrects". The user then resets a password that was correct.
    const loginFallback = 'Identifiants incorrects';

    test('a receive timeout is a server message, not "Identifiants incorrects"', () {
      final msg = apiErrorMessage(withType(DioExceptionType.receiveTimeout), loginFallback);
      expect(msg, isNot(loginFallback));
      expect(msg.toLowerCase(), contains('serveur'));
    });

    test('a send timeout is a server message, not the fallback', () {
      final msg = apiErrorMessage(withType(DioExceptionType.sendTimeout), loginFallback);
      expect(msg, isNot(loginFallback));
      expect(msg.toLowerCase(), contains('serveur'));
    });

    test('a connection timeout/error is a server message', () {
      for (final t in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.connectionError,
      ]) {
        final msg = apiErrorMessage(withType(t), loginFallback);
        expect(msg, isNot(loginFallback));
        expect(msg.toLowerCase(), contains('serveur'));
      }
    });

    test('a 502/503 cold-start body is NOT reported as wrong credentials', () {
      for (final code in [500, 502, 503]) {
        final msg = apiErrorMessage(withStatus(code, '<html>Bad Gateway</html>'), loginFallback);
        expect(msg, isNot(loginFallback), reason: '$code must not read as bad credentials');
        expect(msg.toLowerCase(), contains('serveur'));
      }
    });

    test('a genuine 401 with no JSON detail still shows the caller fallback', () {
      // This is the ONLY case the login fallback is meant for.
      final msg = apiErrorMessage(withStatus(401), loginFallback);
      expect(msg, loginFallback);
    });

    test('a server-provided detail wins over the fallback', () {
      final msg = apiErrorMessage(
        withStatus(400, {'detail': 'Ce compte est désactivé.'}),
        loginFallback,
      );
      expect(msg, 'Ce compte est désactivé.');
    });

    test('FastAPI validation errors are flattened to their messages', () {
      final msg = apiErrorMessage(withStatus(422, {
        'detail': [
          {'msg': 'champ requis', 'loc': ['body', 'email']},
        ],
      }));
      expect(msg, 'champ requis');
    });
  });
}
