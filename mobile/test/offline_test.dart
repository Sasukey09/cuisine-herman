import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:cuisine_herman_mobile/core/offline_cache.dart';
import 'package:cuisine_herman_mobile/core/outbox.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  // ------------------------------------------------------------------------ //
  // The distinction the whole offline story rests on.
  //
  // "No network" must be retried; "the server said no" must not. Confusing the
  // two means either retrying a 400 forever, or throwing away the chef's work
  // because the wifi blinked.
  // ------------------------------------------------------------------------ //
  group('offline vs refused', () {
    final req = RequestOptions(path: '/products/');

    test('a lost connection is an offline error', () {
      for (final type in [
        DioExceptionType.connectionError,
        DioExceptionType.connectionTimeout,
        DioExceptionType.receiveTimeout,
        DioExceptionType.sendTimeout,
      ]) {
        expect(
          isOfflineError(DioException(requestOptions: req, type: type)),
          isTrue,
          reason: '$type should be treated as offline',
        );
      }
    });

    test('a server refusal is NOT an offline error', () {
      final refused = DioException(
        requestOptions: req,
        type: DioExceptionType.badResponse,
        response: Response(requestOptions: req, statusCode: 400),
      );
      expect(isOfflineError(refused), isFalse,
          reason: 'a 400 queued and retried forever would hide the problem');
    });

    test('a non-Dio error is not an offline error', () {
      expect(isOfflineError(StateError('boom')), isFalse);
    });
  });

  // ------------------------------------------------------------------------ //
  // The queue survives the app being killed — that is the entire point.
  // ------------------------------------------------------------------------ //
  group('outbox', () {
    test('a queued write survives a restart', () async {
      final prefs = await SharedPreferences.getInstance();
      final outbox = Outbox(prefs, _neverSends);

      await outbox.enqueue(
        path: '/products/',
        body: {'name': 'Beurre doux'},
        label: 'Produit : Beurre doux',
      );

      // A brand new Outbox, as if the app had been killed and reopened.
      final reopened = Outbox(await SharedPreferences.getInstance(), _neverSends);
      final pending = reopened.list();

      expect(pending, hasLength(1));
      expect(pending.first.label, 'Produit : Beurre doux');
      expect(pending.first.body['name'], 'Beurre doux');
    });

    test('removing a write empties the queue', () async {
      final outbox = Outbox(await SharedPreferences.getInstance(), _neverSends);
      await outbox.enqueue(path: '/products/', body: {'name': 'X'}, label: 'X');
      await outbox.remove(outbox.list().first.id);
      expect(outbox.list(), isEmpty);
    });

    test('a corrupted queue reads as empty instead of crashing', () async {
      SharedPreferences.setMockInitialValues({'outbox': 'not json at all'});
      final outbox = Outbox(await SharedPreferences.getInstance(), _neverSends);
      expect(outbox.list(), isEmpty);
    });
  });

  // ------------------------------------------------------------------------ //
  // Cached data is never presented as if it were live.
  // ------------------------------------------------------------------------ //
  group('cache', () {
    test('what goes in comes out, with its age', () async {
      final cache = await OfflineCache.open();
      await cache.write('products', [
        {'name': 'Beurre'}
      ]);

      final payload = cache.read('products');
      expect(payload, isNotNull);
      expect((payload!.data as List).first['name'], 'Beurre');
      expect(payload.age.inSeconds, lessThan(5));
    });

    test('an unknown key reads as nothing', () async {
      final cache = await OfflineCache.open();
      expect(cache.read('never-written'), isNull);
    });

    test('the age is always spelled out for the user', () {
      expect(formatAge(const Duration(seconds: 20)), "à l'instant");
      expect(formatAge(const Duration(minutes: 8)), 'il y a 8 min');
      expect(formatAge(const Duration(hours: 5)), 'il y a 5 h');
      expect(formatAge(const Duration(days: 2)), 'il y a 2 j');
    });
  });
}

/// The queue tests never reach the network.
Future<void> _neverSends(String path, Map<String, dynamic> body) async =>
    throw StateError('the queue tests must not send anything');
