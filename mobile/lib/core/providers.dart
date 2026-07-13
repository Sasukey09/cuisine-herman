import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'offline_cache.dart';
import 'outbox.dart';
import 'token_store.dart';

final tokenStoreProvider = Provider<TokenStore>((ref) => TokenStore());

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(ref.read(tokenStoreProvider));
});

final offlineCacheProvider = FutureProvider<OfflineCache>((ref) => OfflineCache.open());

final outboxProvider = FutureProvider<Outbox>((ref) async {
  return Outbox.open(ref.read(apiClientProvider));
});

/// Where the data on screen actually came from.
enum Freshness { live, cached }

class Loaded {
  const Loaded(this.data, this.freshness, {this.age});
  final dynamic data;
  final Freshness freshness;
  final Duration? age;

  bool get isStale => freshness == Freshness.cached;
}

/// Fetch, and fall back to the last known good answer when the network is gone.
///
/// This is the whole offline story for reads. A kitchen has no signal in the
/// cellar or the walk-in, and every screen used to go blank there.
///
/// A successful response is written to the cache. A *connection* failure serves
/// the cache instead — always labelled with its age, because a stale cost shown
/// as current is worse than no cost at all: the chef would price a dish on it.
///
/// A failure the SERVER produced (401, 500…) is deliberately NOT swallowed:
/// showing yesterday's prices because the token expired would hide a real
/// problem behind plausible data.
Future<Loaded> fetchWithCache(
  Ref ref, {
  required String cacheKey,
  required Future<dynamic> Function() request,
}) async {
  final cache = await ref.read(offlineCacheProvider.future);

  try {
    final data = await request();
    await cache.write(cacheKey, data);

    // Back online: push whatever the user created while offline.
    final outbox = await ref.read(outboxProvider.future);
    await outbox.flush();

    return Loaded(data, Freshness.live);
  } catch (error) {
    if (!isOfflineError(error)) rethrow;

    final cached = cache.read(cacheKey);
    if (cached == null) rethrow; // nothing to fall back on: let the error show
    return Loaded(cached.data, Freshness.cached, age: cached.age);
  }
}
