import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:foodgad_mobile/core/api_client.dart';
import 'package:foodgad_mobile/core/token_store.dart';

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  // ---------------------------------------------------------------------- //
  // Regression: without finite timeouts, a request that connects but never
  // answers (Render cold start / stalled proxy) neither returns nor throws, so
  // the launch `me()` call hangs and the app sits on a spinner forever. The
  // client MUST always carry finite connect/receive timeouts.
  // ---------------------------------------------------------------------- //
  test('the API client is configured with finite timeouts', () {
    final client = ApiClient(TokenStore());
    expect(client.dio.options.connectTimeout, isNotNull);
    expect(client.dio.options.receiveTimeout, isNotNull);
    expect(client.dio.options.connectTimeout! > Duration.zero, isTrue);
    expect(client.dio.options.receiveTimeout! > Duration.zero, isTrue);
  });
}
