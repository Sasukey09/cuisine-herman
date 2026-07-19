import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kTerracotta, kSidebar, kMuted;

class _Msg {
  _Msg(this.role, this.content);
  final String role; // 'user' | 'assistant'
  final String content;
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

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _sending) return;

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
      setState(() {
        _conversationId = data['conversation_id'] as String? ?? _conversationId;
        _messages.add(_Msg('assistant', data['reply'] as String? ?? ''));
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
      }
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
        Expanded(
          child: _restoring
              ? const Center(child: CircularProgressIndicator())
              : _messages.isEmpty
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(28),
                    child: Text(
                      'Posez une question : coûts, marges, optimisations, '
                      'remplacements d\'ingrédients…',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: kMuted),
                    ),
                  ),
                )
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
                    onTap: _sending ? null : _send,
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
            child: Container(
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
          ),
        ],
      ),
    );
  }
}
