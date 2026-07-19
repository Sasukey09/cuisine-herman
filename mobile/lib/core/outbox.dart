import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

/// Writes made while offline, replayed once the network is back.
///
/// Without this, tapping "Créer" in the cellar simply lost the product: an error
/// toast, and the chef's work was gone. The intent is now kept on the device and
/// sent as soon as a request succeeds again.
///
/// Scope is deliberately narrow: only CREATIONS are queued (product, supplier,
/// recipe). Creations cannot conflict — the server assigns the id, and two
/// people adding the same product just get two rows, which is visible and
/// fixable. Queuing edits and deletions would mean resolving genuine conflicts
/// (who wins when both changed the same price?), and guessing that wrong
/// silently corrupts costs. That is a decision to take deliberately, not a
/// feature to sneak in.
class PendingWrite {
  PendingWrite({
    required this.id,
    required this.path,
    required this.body,
    required this.label,
    required this.queuedAt,
    this.attempts = 0,
  });

  final String id;
  final String path;
  final Map<String, dynamic> body;

  /// What the user sees in the pending list ("Produit : Beurre doux").
  final String label;
  final DateTime queuedAt;
  int attempts;

  Map<String, dynamic> toJson() => {
        'id': id,
        'path': path,
        'body': body,
        'label': label,
        'queuedAt': queuedAt.toIso8601String(),
        'attempts': attempts,
      };

  static PendingWrite fromJson(Map<String, dynamic> j) => PendingWrite(
        id: '${j['id']}',
        path: '${j['path']}',
        body: (j['body'] as Map).cast<String, dynamic>(),
        label: '${j['label']}',
        queuedAt: DateTime.tryParse('${j['queuedAt']}') ?? DateTime.now(),
        attempts: (j['attempts'] as num?)?.toInt() ?? 0,
      );
}

/// Sends one queued write. A function rather than a client, so the queue's
/// behaviour (what is retried, what is dropped) can be tested without a network
/// stack — and that behaviour is the part that can lose the user's work.
typedef WriteSender = Future<void> Function(String path, Map<String, dynamic> body);

class Outbox {
  Outbox(this._prefs, this._send);

  final SharedPreferences _prefs;
  final WriteSender _send;

  static const _key = 'outbox';

  /// A write rejected this many times is a write the server will never accept
  /// (a 400, a duplicate…). Retrying forever would hide the failure and keep
  /// the queue growing behind the user's back.
  static const maxAttempts = 3;

  static Future<Outbox> open(ApiClient api) async => Outbox(
        await SharedPreferences.getInstance(),
        (path, body) => api.dio.post(path, data: body),
      );

  List<PendingWrite> list() {
    final raw = _prefs.getString(_key);
    if (raw == null) return [];
    try {
      return (jsonDecode(raw) as List)
          .map((e) => PendingWrite.fromJson((e as Map).cast<String, dynamic>()))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _save(List<PendingWrite> items) async {
    await _prefs.setString(_key, jsonEncode(items.map((e) => e.toJson()).toList()));
  }

  Future<void> enqueue({
    required String path,
    required Map<String, dynamic> body,
    required String label,
  }) async {
    final items = list()
      ..add(PendingWrite(
        id: DateTime.now().microsecondsSinceEpoch.toString(),
        path: path,
        body: body,
        label: label,
        queuedAt: DateTime.now(),
      ));
    await _save(items);
  }

  Future<void> remove(String id) async {
    await _save(list().where((e) => e.id != id).toList());
  }

  /// Drop every pending write. Called on logout so one account's un-synced
  /// offline writes are never replayed under whoever logs in next on the same
  /// device (that would post them into the wrong tenant).
  Future<void> clear() async {
    await _prefs.remove(_key);
  }

  /// Replay the queue. Returns how many writes finally landed.
  ///
  /// Stops at the first network failure: if the connection is still down there
  /// is no point burning the retry budget of every remaining item.
  Future<int> flush() async {
    final items = list();
    if (items.isEmpty) return 0;

    var sent = 0;
    final remaining = <PendingWrite>[];

    for (final item in items) {
      try {
        await _send(item.path, item.body);
        sent++;
      } on DioException catch (e) {
        if (_isOffline(e)) {
          // Still no network: keep this one and everything after it, untouched.
          remaining.add(item);
          remaining.addAll(items.sublist(items.indexOf(item) + 1));
          break;
        }
        // The server answered and refused. Count it; drop it once it is clear
        // it will never be accepted.
        item.attempts++;
        if (item.attempts < maxAttempts) remaining.add(item);
      } catch (_) {
        item.attempts++;
        if (item.attempts < maxAttempts) remaining.add(item);
      }
    }

    await _save(remaining);
    return sent;
  }
}

/// Is this a "no network" failure, as opposed to the server saying no?
///
/// The distinction matters: a 400 must not be retried forever, and a lost
/// connection must not be treated as a rejection.
bool isOfflineError(Object error) =>
    error is DioException && _isOffline(error);

bool _isOffline(DioException e) =>
    e.type == DioExceptionType.connectionError ||
    e.type == DioExceptionType.connectionTimeout ||
    e.type == DioExceptionType.receiveTimeout ||
    e.type == DioExceptionType.sendTimeout ||
    (e.type == DioExceptionType.unknown && e.response == null);
