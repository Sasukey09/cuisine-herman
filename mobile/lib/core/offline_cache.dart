import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Last known good answer for a given endpoint, kept on the device.
///
/// A kitchen has terrible reception: the walk-in fridge, the cellar, the back of
/// the restaurant. Until now every screen went blank the moment the signal did.
/// Now the last data we successfully fetched is shown instead — but ALWAYS
/// labelled with its age, because a stale cost silently presented as current is
/// worse than no cost at all: the chef would price a dish on it.
class CachedPayload {
  const CachedPayload(this.data, this.fetchedAt);
  final dynamic data;
  final DateTime fetchedAt;

  Duration get age => DateTime.now().difference(fetchedAt);
}

class OfflineCache {
  OfflineCache(this._prefs);
  final SharedPreferences _prefs;

  static const _prefix = 'cache:';

  static Future<OfflineCache> open() async =>
      OfflineCache(await SharedPreferences.getInstance());

  Future<void> write(String key, dynamic data) async {
    await _prefs.setString(
      '$_prefix$key',
      jsonEncode({
        'at': DateTime.now().toIso8601String(),
        'data': data,
      }),
    );
  }

  CachedPayload? read(String key) {
    final raw = _prefs.getString('$_prefix$key');
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      final at = DateTime.tryParse('${map['at']}');
      if (at == null) return null;
      return CachedPayload(map['data'], at);
    } catch (_) {
      return null; // corrupted entry: behave as if we had nothing
    }
  }

  Future<void> clear() async {
    for (final key in _prefs.getKeys().where((k) => k.startsWith(_prefix)).toList()) {
      await _prefs.remove(key);
    }
  }
}

/// "il y a 3 min" — the age is shown next to cached data, never hidden.
String formatAge(Duration age) {
  if (age.inMinutes < 1) return "à l'instant";
  if (age.inMinutes < 60) return 'il y a ${age.inMinutes} min';
  if (age.inHours < 24) return 'il y a ${age.inHours} h';
  return 'il y a ${age.inDays} j';
}
