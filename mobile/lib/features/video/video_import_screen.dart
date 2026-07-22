import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:youtube_explode_dart/youtube_explode_dart.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood;

/// Video/audio file for the reliable fallback import (POST /video/extract-file).
/// `uniformTypeIdentifiers` are REQUIRED on iOS (file_selector throws without
/// them — the exact bug that killed the invoice picker on iPhone).
const _videoFiles = XTypeGroup(
  label: 'Vidéo / audio',
  extensions: ['mp4', 'mov', 'm4v', 'webm', 'mkv', 'avi', 'mp3', 'm4a', 'wav', 'aac'],
  mimeTypes: [
    'video/mp4', 'video/quicktime', 'video/webm', 'video/x-matroska',
    'audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/aac',
  ],
  uniformTypeIdentifiers: ['public.movie', 'public.audio'],
);

class _Ing {
  _Ing(this.name, this.qty, this.unit);
  String name;
  String qty;
  String unit;
}

class VideoImportScreen extends ConsumerStatefulWidget {
  const VideoImportScreen({super.key});

  @override
  ConsumerState<VideoImportScreen> createState() => _VideoImportScreenState();
}

class _VideoImportScreenState extends ConsumerState<VideoImportScreen> {
  final _url = TextEditingController();
  final _name = TextEditingController();
  final _portions = TextEditingController();
  final _steps = TextEditingController(); // one step per line, like the web
  final List<_Ing> _ings = [];
  bool _extracting = false;
  bool _saving = false;
  bool _hasDraft = false;
  String? _savedInfo;

  @override
  void dispose() {
    _url.dispose();
    _name.dispose();
    _portions.dispose();
    _steps.dispose();
    super.dispose();
  }

  static bool _isYoutube(String url) {
    final u = url.toLowerCase();
    return u.contains('youtube.com') || u.contains('youtu.be');
  }

  /// Fetch the captions FROM the phone (residential IP), which YouTube does not
  /// bot-block like the server's datacenter IP. Returns null if unavailable.
  Future<({String text, String title})?> _fetchYoutubeCaptions(String url) async {
    final yt = YoutubeExplode();
    try {
      final video = await yt.videos.get(url);
      final manifest = await yt.videos.closedCaptions.getManifest(video.id);
      if (manifest.tracks.isEmpty) return null;
      ClosedCaptionTrackInfo pick() {
        for (final lang in ['fr', 'en']) {
          final m = manifest.tracks
              .where((t) => t.language.code.toLowerCase().startsWith(lang));
          if (m.isNotEmpty) return m.first;
        }
        return manifest.tracks.first;
      }

      final track = await yt.videos.closedCaptions.get(pick());
      final text = track.captions
          .map((c) => c.text)
          .where((t) => t.trim().isNotEmpty)
          .join(' ')
          .trim();
      if (text.isEmpty) return null;
      return (text: text, title: video.title);
    } catch (_) {
      return null; // pas de sous-titres accessibles -> on tentera le serveur
    } finally {
      yt.close();
    }
  }

  Future<void> _extract() async {
    final url = _url.text.trim();
    if (url.isEmpty || _extracting) return;
    setState(() {
      _extracting = true;
      _savedInfo = null;
    });
    try {
      final api = ref.read(apiClientProvider).dio;
      Map<String, dynamic> data;
      // YouTube : récupérer les sous-titres côté téléphone (IP résidentielle,
      // non bloquée) puis les envoyer au backend. Repli serveur si indisponible.
      final caps = _isYoutube(url) ? await _fetchYoutubeCaptions(url) : null;
      if (caps != null) {
        final resp = await api.post('/video/extract-transcript',
            data: {'transcript': caps.text, 'url': url, 'title': caps.title});
        data = resp.data as Map<String, dynamic>;
      } else {
        final resp = await api.post('/video/extract', data: {'url': url});
        data = resp.data as Map<String, dynamic>;
      }
      _applyDraft(data);
      _snack('Recette extraite — vérifiez les quantités estimées.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _extracting = false);
    }
  }

  /// Populate the editable draft from an extract response (shared by URL import
  /// and file import). Reads name, portions, ingredients AND steps.
  void _applyDraft(Map<String, dynamic> data) {
    final draft = data['draft'] as Map<String, dynamic>;
    _name.text = (draft['name'] as String?) ?? '';
    _portions.text = draft['yield_qty'] != null ? '${draft['yield_qty']}' : '';
    _ings
      ..clear()
      ..addAll(((draft['ingredients'] as List?) ?? []).map((e) {
        final m = e as Map<String, dynamic>;
        return _Ing('${m['name'] ?? ''}', m['qty'] != null ? '${m['qty']}' : '', '${m['unit'] ?? ''}');
      }));
    // Procédure : l'IA renvoie draft['steps'] (une liste). Avant ce correctif,
    // le mobile l'ignorait et enregistrait la recette sans instructions.
    _steps.text = ((draft['steps'] as List?) ?? []).map((e) => '$e').join('\n');
    setState(() => _hasDraft = true);
  }

  /// Reliable fallback: pick a video/audio FILE and let the server transcribe it
  /// (Whisper). Works where URL import can't — TikTok/Insta/FB (server IP is
  /// blocked) or a YouTube video without captions. Mirrors the web file import.
  Future<void> _extractFile() async {
    if (_extracting) return;
    final XFile? file;
    try {
      file = await openFile(acceptedTypeGroups: const [_videoFiles]);
    } catch (_) {
      _snack("Impossible d'ouvrir le sélecteur de fichiers.");
      return;
    }
    if (file == null) return;
    setState(() {
      _extracting = true;
      _savedInfo = null;
    });
    try {
      final bytes = await file.readAsBytes();
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: file.name),
      });
      final resp = await ref.read(apiClientProvider).dio.post(
            '/video/extract-file',
            data: form,
            options: Options(
              sendTimeout: const Duration(seconds: 180),
              receiveTimeout: const Duration(seconds: 180),
            ),
          );
      _applyDraft(resp.data as Map<String, dynamic>);
      _snack('Recette extraite du fichier — vérifiez les quantités.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _extracting = false);
    }
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) {
      _snack('Donnez un nom à la recette.');
      return;
    }
    setState(() => _saving = true);
    try {
      final ingredients = _ings
          .where((i) => i.name.trim().isNotEmpty)
          .map((i) => {
                'name': i.name.trim(),
                'qty': i.qty.trim().isEmpty ? null : double.tryParse(i.qty.trim()),
                'unit': i.unit.trim().isEmpty ? null : i.unit.trim(),
              })
          .toList();
      final steps = _steps.text
          .split('\n')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
      final resp = await ref.read(apiClientProvider).dio.post('/video/save', data: {
        'name': _name.text.trim(),
        'yield_qty': _portions.text.trim().isEmpty ? null : double.tryParse(_portions.text.trim()),
        'ingredients': ingredients,
        'steps': steps,
      });
      final cost = (resp.data as Map<String, dynamic>)['cost'] as Map<String, dynamic>;
      setState(() =>
          _savedInfo = 'Fiche enregistrée. Coût/portion : ${cost['cost_per_portion'] ?? 0} €');
      _snack('Fiche enregistrée et chiffrée.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _snack(String m) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
      children: [
        // --- Drop-zone card ----------------------------------------------
        MockCard(
          padding: const EdgeInsets.all(18),
          child: Container(
            padding: const EdgeInsets.fromLTRB(16, 22, 16, 16),
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              border: Border.all(color: Theme.of(context).dividerColor, width: 2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                const Text('🎬', style: TextStyle(fontSize: 30)),
                const SizedBox(height: 4),
                const Text('Importez une vidéo',
                    style: TextStyle(fontFamily: 'Newsreader', fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                const Text("Lien YouTube / Instagram / TikTok / Facebook. L'IA extrait les ingrédients.",
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: kMuted)),
                const SizedBox(height: 12),
                TextField(
                  controller: _url,
                  style: const TextStyle(fontSize: 13),
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: 'https://…',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(9),
                      borderSide: BorderSide(color: Theme.of(context).dividerColor),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: GradientButton(
                    label: 'Analyser',
                    onPressed: _extracting ? null : _extract,
                    expand: true,
                    loading: _extracting,
                  ),
                ),
                const SizedBox(height: 4),
                TextButton.icon(
                  onPressed: _extracting ? null : _extractFile,
                  icon: const Icon(Icons.upload_file, size: 18),
                  label: const Text('Ou importer un fichier vidéo/audio'),
                ),
              ],
            ),
          ),
        ),

        // --- Extracted recipe card ---------------------------------------
        if (_hasDraft) ...[
          const SizedBox(height: 13),
          MockCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Recette extraite',
                    style: TextStyle(fontFamily: 'Newsreader', fontSize: 15.5, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                const Text('Quantités estimées — à valider',
                    style: TextStyle(fontSize: 12, color: kMuted)),
                const SizedBox(height: 12),
                TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nom')),
                const SizedBox(height: 8),
                TextField(
                  controller: _portions,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Portions'),
                ),
                const SizedBox(height: 12),
                const Text('Ingrédients',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                ..._ings.asMap().entries.map((e) {
                  final i = e.key;
                  final ing = e.value;
                  return Container(
                    decoration: const BoxDecoration(
                      border: Border(bottom: BorderSide(color: Color(0xFFECE4D4))),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(right: 4),
                          child: Text('✓', style: TextStyle(color: kGood, fontSize: 13)),
                        ),
                        Expanded(
                          flex: 3,
                          child: TextFormField(
                            initialValue: ing.name,
                            style: const TextStyle(fontSize: 13),
                            decoration: const InputDecoration(
                                isDense: true, border: InputBorder.none, hintText: 'Ingrédient'),
                            onChanged: (v) => ing.name = v,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: TextFormField(
                            initialValue: ing.qty,
                            keyboardType: TextInputType.number,
                            style: const TextStyle(fontSize: 13),
                            decoration: const InputDecoration(
                                isDense: true, border: InputBorder.none, hintText: 'Qté'),
                            onChanged: (v) => ing.qty = v,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: TextFormField(
                            initialValue: ing.unit,
                            style: const TextStyle(fontSize: 13),
                            decoration: const InputDecoration(
                                isDense: true, border: InputBorder.none, hintText: 'unité'),
                            onChanged: (v) => ing.unit = v,
                          ),
                        ),
                        InkWell(
                          onTap: () => setState(() => _ings.removeAt(i)),
                          child: const Padding(
                            padding: EdgeInsets.only(left: 4),
                            child: Icon(Icons.close, size: 16, color: kMuted),
                          ),
                        ),
                      ],
                    ),
                  );
                }),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => setState(() => _ings.add(_Ing('', '', ''))),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Ajouter un ingrédient'),
                  ),
                ),
                const SizedBox(height: 12),
                const Text('Étapes',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                const Text('Une étape par ligne',
                    style: TextStyle(fontSize: 11.5, color: kMuted)),
                const SizedBox(height: 6),
                TextField(
                  controller: _steps,
                  minLines: 3,
                  maxLines: 8,
                  style: const TextStyle(fontSize: 13),
                  decoration: InputDecoration(
                    hintText: 'Faire revenir les oignons…\nAjouter le riz…',
                    isDense: true,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(9),
                      borderSide: BorderSide(color: Theme.of(context).dividerColor),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: GradientButton(
                    label: 'Créer la recette',
                    onPressed: _saving ? null : _save,
                    expand: true,
                    loading: _saving,
                  ),
                ),
                if (_savedInfo != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(_savedInfo!, style: const TextStyle(color: kGood)),
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
