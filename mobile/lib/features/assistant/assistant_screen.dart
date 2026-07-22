import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kTerracotta, kSidebar, kMuted, kBad;

/// Prompts worth asking *for this restaurant* (GET /ai/suggestions).
/// autoDispose: refetched each time the empty state is shown again.
final _suggestionsProvider = FutureProvider.autoDispose<List<String>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/ai/suggestions');
  final data = resp.data as Map<String, dynamic>;
  return ((data['suggestions'] as List?) ?? []).map((e) => '$e').toList();
});

/// Saved threads for the current user (GET /ai/conversations), newest first.
final _conversationsProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
  final api = ref.read(apiClientProvider);
  final resp = await api.dio.get('/ai/conversations');
  return ((resp.data as List?) ?? [])
      .map((e) => (e as Map).cast<String, dynamic>())
      .toList();
});

class _Msg {
  _Msg(this.role, this.content, {this.toolNames = const []});
  final String role; // 'user' | 'assistant'
  final String content;
  // Tools the assistant reported using for this reply (AIChatResponse.tool_calls).
  final List<String> toolNames;
}

class AssistantScreen extends ConsumerStatefulWidget {
  const AssistantScreen({super.key});

  @override
  ConsumerState<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends ConsumerState<AssistantScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_Msg> _messages = [];
  bool _sending = false;
  // The thread lives on the server now: killing the app no longer erases it.
  String? _conversationId;
  bool _restoring = true;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _restoreLastConversation();
  }

  /// Reopen the most recent thread instead of a blank screen.
  Future<void> _restoreLastConversation() async {
    try {
      final api = ref.read(apiClientProvider);
      final list = await api.dio.get('/ai/conversations');
      final rows = (list.data as List);
      if (rows.isNotEmpty) {
        final id = '${(rows.first as Map)['id']}';
        final detail = await api.dio.get('/ai/conversations/$id');
        final msgs = ((detail.data as Map)['messages'] as List?) ?? [];
        if (mounted) {
          setState(() {
            _conversationId = id;
            _messages
              ..clear()
              ..addAll(msgs.map((m) => _Msg('${(m as Map)['role']}', '${m['content']}')));
          });
          _scrollToEnd();
        }
      }
    } catch (_) {
      // offline or empty: start fresh rather than block the screen
    } finally {
      if (mounted) setState(() => _restoring = false);
    }
  }

  /// Blank slate: drop the current thread id and its messages.
  void _startNew() {
    if (_sending) return;
    setState(() {
      _conversationId = null;
      _messages.clear();
      _input.clear();
    });
  }

  /// Replay a saved thread into the view.
  Future<void> _loadConversation(String id) async {
    final api = ref.read(apiClientProvider);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final detail = await api.dio.get('/ai/conversations/$id');
      final msgs = ((detail.data as Map)['messages'] as List?) ?? [];
      if (!mounted) return;
      setState(() {
        _conversationId = id;
        _messages
          ..clear()
          ..addAll(msgs.map((m) => _Msg('${(m as Map)['role']}', '${m['content']}')));
      });
      _scrollToEnd();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _deleteConversation(String id) async {
    final api = ref.read(apiClientProvider);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await api.dio.delete('/ai/conversations/$id');
      ref.invalidate(_conversationsProvider);
      // If the open thread was the one just deleted, fall back to a blank slate.
      if (id == _conversationId && mounted) _startNew();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  Future<void> _confirmAndDelete(BuildContext sheetCtx, String id) async {
    final ok = await showDialog<bool>(
      context: sheetCtx,
      builder: (dctx) => AlertDialog(
        title: const Text('Supprimer la conversation ?'),
        content: const Text('Cette action est définitive.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dctx).pop(false),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: kBad),
            child: const Text('Supprimer'),
          ),
        ],
      ),
    );
    if (ok == true) await _deleteConversation(id);
  }

  /// Bottom sheet listing saved threads: tap to open, swipe icon to delete.
  void _openHistory() {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetCtx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 20),
          child: Consumer(
            builder: (ctx, sheetRef, _) {
              final async = sheetRef.watch(_conversationsProvider);
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 42,
                      height: 5,
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: Theme.of(ctx).dividerColor,
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      const Text('Conversations',
                          style: TextStyle(
                              fontFamily: 'Newsreader',
                              fontSize: 19,
                              fontWeight: FontWeight.w600)),
                      const Spacer(),
                      TextButton.icon(
                        onPressed: () {
                          Navigator.of(sheetCtx).pop();
                          _startNew();
                        },
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('Nouvelle'),
                        style: TextButton.styleFrom(foregroundColor: kTerracotta),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  async.when(
                    loading: () => const Padding(
                      padding: EdgeInsets.all(24),
                      child: Center(child: CircularProgressIndicator()),
                    ),
                    error: (e, _) => Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(apiErrorMessage(e),
                          style: const TextStyle(color: kMuted, fontSize: 13)),
                    ),
                    data: (rows) {
                      if (rows.isEmpty) {
                        return const Padding(
                          padding: EdgeInsets.symmetric(vertical: 24),
                          child: Text('Aucune conversation enregistrée.',
                              style: TextStyle(color: kMuted, fontSize: 13)),
                        );
                      }
                      return ConstrainedBox(
                        constraints: BoxConstraints(
                            maxHeight: MediaQuery.of(ctx).size.height * 0.5),
                        child: ListView.separated(
                          shrinkWrap: true,
                          itemCount: rows.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 6),
                          itemBuilder: (_, i) {
                            final c = rows[i];
                            final id = '${c['id']}';
                            final title = (c['title'] as String?)?.trim();
                            return _ConversationTile(
                              title: (title == null || title.isEmpty)
                                  ? 'Conversation'
                                  : title,
                              selected: id == _conversationId,
                              onTap: () {
                                Navigator.of(sheetCtx).pop();
                                _loadConversation(id);
                              },
                              onDelete: () => _confirmAndDelete(sheetCtx, id),
                            );
                          },
                        ),
                      );
                    },
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? _input.text).trim();
    if (text.isEmpty || _sending) return;

    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _messages.add(_Msg('user', text));
      _sending = true;
      _input.clear();
    });
    _scrollToEnd();

    try {
      final api = ref.read(apiClientProvider);
      final resp = await api.dio.post('/ai/chat', data: {
        'message': text,
        'conversation_id': _conversationId,
      });
      final data = resp.data as Map<String, dynamic>;
      final tools = ((data['tool_calls'] as List?) ?? [])
          .map((t) => '${(t as Map)['name']}')
          .where((n) => n.isNotEmpty)
          .toList();
      if (!mounted) return;
      setState(() {
        _conversationId = data['conversation_id'] as String? ?? _conversationId;
        _messages.add(_Msg('assistant', data['reply'] as String? ?? '', toolNames: tools));
      });
      // Keep the history list (and its ordering) in sync with the new turn.
      ref.invalidate(_conversationsProvider);
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    } finally {
      if (mounted) setState(() => _sending = false);
      _scrollToEnd();
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Toolbar: the shell owns the page title, so New/History live here.
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 0, 6, 2),
          child: Row(
            children: [
              TextButton.icon(
                onPressed: _sending ? null : _startNew,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Nouvelle'),
                style: TextButton.styleFrom(foregroundColor: kTerracotta),
              ),
              const Spacer(),
              IconButton(
                tooltip: 'Historique des conversations',
                onPressed: _openHistory,
                icon: const Icon(Icons.history, color: kMuted),
              ),
            ],
          ),
        ),
        Expanded(
          child: _restoring
              ? const Center(child: CircularProgressIndicator())
              : _messages.isEmpty
                  ? _EmptyState(onPick: _send)
                  : ListView.builder(
                      controller: _scroll,
                      padding: const EdgeInsets.fromLTRB(18, 6, 18, 8),
                      itemCount: _messages.length,
                      itemBuilder: (context, i) => _Bubble(_messages[i]),
                    ),
        ),
        if (_sending) const LinearProgressIndicator(minHeight: 2, color: kTerracotta),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 6, 14, 10),
            child: Container(
              decoration: BoxDecoration(
                color: Theme.of(context).cardColor,
                border: Border.all(color: Theme.of(context).dividerColor),
                borderRadius: BorderRadius.circular(14),
              ),
              padding: const EdgeInsets.fromLTRB(14, 5, 5, 5),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: TextField(
                      controller: _input,
                      minLines: 1,
                      maxLines: 4,
                      style: const TextStyle(fontSize: 13),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: const InputDecoration(
                        isCollapsed: true,
                        border: InputBorder.none,
                        hintText: 'Écrivez votre question…',
                        hintStyle: TextStyle(fontSize: 13, color: kMuted),
                        contentPadding: EdgeInsets.symmetric(vertical: 8),
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  InkWell(
                    borderRadius: BorderRadius.circular(9),
                    onTap: _sending ? null : () => _send(),
                    child: Container(
                      width: 34,
                      height: 34,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: kTerracotta,
                        borderRadius: BorderRadius.circular(9),
                      ),
                      child: const Icon(Icons.arrow_upward, color: Colors.white, size: 18),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Empty-thread state: intro line + per-tenant suggestion chips.
class _EmptyState extends ConsumerWidget {
  const _EmptyState({required this.onPick});
  final void Function(String) onPick;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final suggestions = ref.watch(_suggestionsProvider);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
      child: Column(
        children: [
          Container(
            width: 52,
            height: 52,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: kSidebar,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Text('✦', style: TextStyle(color: Color(0xFFD98C5F), fontSize: 22)),
          ),
          const SizedBox(height: 16),
          const Text(
            "L'assistant connaît déjà la situation de votre restaurant. "
            "Voici ce qu'il y a à regarder chez vous :",
            textAlign: TextAlign.center,
            style: TextStyle(color: kMuted, fontSize: 13, height: 1.5),
          ),
          const SizedBox(height: 18),
          suggestions.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(8),
              child: SizedBox(
                  width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
            ),
            error: (_, __) => const SizedBox.shrink(),
            data: (items) => Wrap(
              alignment: WrapAlignment.center,
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final s in items) _SuggestionChip(s, onTap: () => onPick(s)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SuggestionChip extends StatelessWidget {
  const _SuggestionChip(this.text, {required this.onTap});
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 340),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: kTerracotta.withValues(alpha: .10),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          text,
          style: const TextStyle(
              fontSize: 12.5, color: kTerracotta, fontWeight: FontWeight.w500),
        ),
      ),
    );
  }
}

class _ConversationTile extends StatelessWidget {
  const _ConversationTile({
    required this.title,
    required this.selected,
    required this.onTap,
    required this.onDelete,
  });
  final String title;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: theme.cardColor,
        border: Border.all(
            color: selected ? kTerracotta : theme.dividerColor,
            width: selected ? 1.4 : 1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Expanded(
            child: InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: onTap,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(13, 12, 8, 12),
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                    color: selected ? kTerracotta : null,
                  ),
                ),
              ),
            ),
          ),
          IconButton(
            tooltip: 'Supprimer',
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.delete_outline, size: 19, color: kMuted),
            onPressed: onDelete,
          ),
        ],
      ),
    );
  }
}

class _ToolBadge extends StatelessWidget {
  const _ToolBadge(this.name);
  final String name;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: kSidebar.withValues(alpha: .06),
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.build_outlined, size: 12, color: kMuted),
          const SizedBox(width: 4),
          Text(name, style: const TextStyle(fontSize: 11, color: kMuted)),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble(this.msg);
  final _Msg msg;

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.of(context).size.width;
    if (msg.role == 'user') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Align(
          alignment: Alignment.centerRight,
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: w * 0.84),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
              decoration: const BoxDecoration(
                color: kTerracotta,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(14),
                  topRight: Radius.circular(14),
                  bottomRight: Radius.circular(4),
                  bottomLeft: Radius.circular(14),
                ),
              ),
              child: Text(msg.content,
                  style: const TextStyle(color: Colors.white, fontSize: 13, height: 1.5)),
            ),
          ),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 26,
            height: 26,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: kSidebar,
              borderRadius: BorderRadius.circular(7),
            ),
            child: const Text('✦', style: TextStyle(color: Color(0xFFD98C5F), fontSize: 12)),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  constraints: BoxConstraints(maxWidth: w * 0.8),
                  padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
                  decoration: BoxDecoration(
                    color: Theme.of(context).cardColor,
                    border: Border.all(color: Theme.of(context).dividerColor),
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(14),
                      topRight: Radius.circular(14),
                      bottomRight: Radius.circular(14),
                      bottomLeft: Radius.circular(4),
                    ),
                  ),
                  child: Text(msg.content, style: const TextStyle(fontSize: 13, height: 1.5)),
                ),
                if (msg.toolNames.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [for (final t in msg.toolNames) _ToolBadge(t)],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
