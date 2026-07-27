import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:youtube_explode_dart/youtube_explode_dart.dart';

import '../../common/format.dart';
import '../../common/ui_kit.dart';
import '../../core/api_error.dart';
import '../../core/providers.dart';
import '../../main.dart' show kMuted, kGood, kWarn;
import '../imports/import_line_editor.dart' show importPill;

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

/// One AI-detected recipe out of a (possibly multi-recipe) video, editable
/// before it is saved. Mirrors the web's `CandidateState`
/// (`frontend/src/features/video/candidate-card.tsx`) and the backend's
/// `VideoRecipeCandidate` (`backend/app/schemas/schemas.py`).
///
/// `id` is a purely client-side, stable identifier (NOT sent to the backend):
/// it keeps a card's expanded/selected state attached to the recipe itself,
/// not its position in the list, when other cards are deleted or merged
/// around it — the same reason the web keeps `crypto.randomUUID()` per card.
class _Candidate {
  _Candidate({
    required this.id,
    this.name = '',
    this.description,
    this.summary,
    this.yieldQty,
    List<_Ing>? ingredients,
    List<String>? steps,
    this.prepTimeMin,
    this.cookTimeMin,
    List<String>? tips,
    List<String>? variants,
    List<String>? allergens,
    this.startSec,
    this.endSec,
  })  : ingredients = ingredients ?? [],
        steps = steps ?? [],
        tips = tips ?? [],
        variants = variants ?? [],
        allergens = allergens ?? [];

  final int id;
  String name;
  String? description;
  String? summary;
  double? yieldQty;
  List<_Ing> ingredients;
  List<String> steps;
  double? prepTimeMin;
  double? cookTimeMin;
  List<String> tips;
  List<String> variants;
  List<String> allergens;
  double? startSec;
  double? endSec;
  // Newly extracted candidates start selected (so "Enregistrer" defaults to
  // saving everything detected) and collapsed (so N recipes don't turn the
  // screen into N open forms at once).
  bool selected = true;
  bool expanded = false;

  factory _Candidate.fromJson(int id, Map<String, dynamic> m) {
    return _Candidate(
      id: id,
      name: '${m['name'] ?? ''}',
      description: m['description'] as String?,
      summary: m['summary'] as String?,
      yieldQty: (m['yield_qty'] as num?)?.toDouble(),
      ingredients: ((m['ingredients'] as List?) ?? const []).map((e) {
        final im = e as Map<String, dynamic>;
        return _Ing(
          '${im['name'] ?? ''}',
          im['qty'] != null ? '${im['qty']}' : '',
          '${im['unit'] ?? ''}',
        );
      }).toList(),
      steps: ((m['steps'] as List?) ?? const []).map((e) => '$e').toList(),
      prepTimeMin: (m['prep_time_min'] as num?)?.toDouble(),
      cookTimeMin: (m['cook_time_min'] as num?)?.toDouble(),
      tips: ((m['tips'] as List?) ?? const []).map((e) => '$e').toList(),
      variants: ((m['variants'] as List?) ?? const []).map((e) => '$e').toList(),
      allergens: ((m['allergens'] as List?) ?? const []).map((e) => '$e').toList(),
      startSec: (m['start_sec'] as num?)?.toDouble(),
      endSec: (m['end_sec'] as num?)?.toDouble(),
    );
  }

  /// What actually goes to POST /video/save (one entry of `recipes`). Blank
  /// ingredient rows and blank step lines are dropped, exactly like the
  /// single-recipe screen used to do — an empty unit/name sent as `""` would
  /// otherwise chase a nonexistent unit or ingredient server-side.
  Map<String, dynamic> toJson() => {
        'name': name.trim(),
        'description': (description ?? '').trim().isEmpty ? null : description!.trim(),
        'summary': (summary ?? '').trim().isEmpty ? null : summary!.trim(),
        'yield_qty': yieldQty,
        'ingredients': ingredients
            .where((i) => i.name.trim().isNotEmpty)
            .map((i) => {
                  'name': i.name.trim(),
                  'qty': i.qty.trim().isEmpty ? null : double.tryParse(i.qty.trim()),
                  'unit': i.unit.trim().isEmpty ? null : i.unit.trim(),
                })
            .toList(),
        'steps': steps.map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
        'prep_time_min': prepTimeMin,
        'cook_time_min': cookTimeMin,
        'tips': tips,
        'variants': variants,
        'allergens': allergens,
        'start_sec': startSec,
        'end_sec': endSec,
      };
}

class VideoImportScreen extends ConsumerStatefulWidget {
  const VideoImportScreen({super.key});

  @override
  ConsumerState<VideoImportScreen> createState() => _VideoImportScreenState();
}

class _VideoImportScreenState extends ConsumerState<VideoImportScreen> {
  final _url = TextEditingController();
  final List<_Candidate> _candidates = [];
  Map<String, dynamic>? _source;
  int _nextId = 0;
  int? _mergeFrom; // id of the card picked as the merge source, if any
  bool _extracting = false;
  bool _saving = false;
  String? _savedInfo;

  @override
  void dispose() {
    _url.dispose();
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
      _applyCandidates(data);
      // The exact count is already the headline just below ("Nous avons
      // détecté N recette(s)") — repeating it here would just be two widgets
      // racing to say the same number.
      _snack(_candidates.length > 1
          ? 'Recettes détectées — vérifiez-les avant d\'enregistrer.'
          : 'Recette extraite — vérifiez les quantités estimées.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _extracting = false);
    }
  }

  /// Populate the candidate cards from an extract response (shared by URL
  /// import and file import): `data['candidates']` (one or more recipes) and
  /// `data['source']` (platform/url/video_id/title/creator/thumbnail), per
  /// `VideoExtractResult` in `backend/app/schemas/schemas.py`.
  void _applyCandidates(Map<String, dynamic> data) {
    final list = (data['candidates'] as List?) ?? const [];
    final source = data['source'] as Map?;
    setState(() {
      _candidates
        ..clear()
        ..addAll(list.map(
            (e) => _Candidate.fromJson(_nextId++, Map<String, dynamic>.from(e as Map))));
      _source = source == null ? null : Map<String, dynamic>.from(source);
      _mergeFrom = null;
    });
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
      _applyCandidates(resp.data as Map<String, dynamic>);
      _snack(_candidates.length > 1
          ? 'Recettes extraites du fichier — vérifiez les quantités.'
          : 'Recette extraite du fichier — vérifiez les quantités.');
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _extracting = false);
    }
  }

  Future<void> _save() async {
    final selected = _candidates.where((c) => c.selected).toList();
    if (selected.isEmpty) {
      _snack('Sélectionnez au moins une recette à enregistrer.');
      return;
    }
    if (selected.any((c) => c.name.trim().isEmpty)) {
      _snack('Donnez un nom à chaque recette sélectionnée.');
      return;
    }
    setState(() => _saving = true);
    // Capture the ORDER of the submitted ids: the backend saves recipe by recipe
    // and returns a partial success (`recipes` + `errors`), each entry carrying
    // the `index` of the recipe it maps to. We map that index back to the card id
    // captured here so we remove ONLY the cards actually persisted — failed ones
    // stay for a retry — keyed off what was submitted, not `.selected` (which the
    // user can keep toggling while the request is in flight).
    final submittedIds = selected.map((c) => c.id).toList();
    try {
      final resp = await ref.read(apiClientProvider).dio.post('/video/save', data: {
        'recipes': selected.map((c) => c.toJson()).toList(),
        'source': _source ?? const {},
      });
      final data = Map<String, dynamic>.from(resp.data as Map);
      final saved = ((data['recipes'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final errors = ((data['errors'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final savedClientIds =
          saved.map((r) => submittedIds[(r['index'] as num).toInt()]).toSet();
      setState(() {
        _candidates.removeWhere((c) => savedClientIds.contains(c.id));
        _mergeFrom = null;
        _savedInfo = saved.isEmpty
            ? null
            : saved.map((r) {
                final cost = Map<String, dynamic>.from((r['cost'] as Map?) ?? const {});
                return '${r['name']} : ${cost['cost_per_portion'] ?? 0} €/portion';
              }).join('  ·  ');
      });
      if (saved.isNotEmpty) {
        _snack(saved.length > 1
            ? '${saved.length} fiches enregistrées et chiffrées.'
            : 'Fiche enregistrée et chiffrée.');
      }
      if (errors.isNotEmpty) {
        _snack('${errors.length} recette(s) non enregistrée(s) : '
            '${errors.map((e) => e['name']).join(', ')}');
      }
    } catch (e) {
      _snack(apiErrorMessage(e));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _deleteCandidate(int id) {
    setState(() {
      _candidates.removeWhere((c) => c.id == id);
      if (_mergeFrom == id) _mergeFrom = null;
    });
  }

  void _toggleSelectAll() {
    final allSelected = _candidates.isNotEmpty && _candidates.every((c) => c.selected);
    setState(() {
      for (final c in _candidates) {
        c.selected = !allSelected;
      }
    });
  }

  /// Two-tap merge, like the web: tap "Fusionner" on a first card to mark it as
  /// the source, then tap it on a second card to fold the source INTO that
  /// second card (ingredients + steps concatenated, tips/variants/allergens
  /// deduplicated, the video time range widened to cover both).
  void _onMergeTap(_Candidate c) {
    if (_candidates.length < 2) return;
    if (_mergeFrom == null) {
      setState(() => _mergeFrom = c.id);
      _snack('Touchez "Fusionner" sur une autre carte pour la fusionner avec celle-ci.');
      return;
    }
    if (_mergeFrom == c.id) {
      setState(() => _mergeFrom = null);
      return;
    }
    _mergeInto(c);
  }

  void _mergeInto(_Candidate target) {
    final fromIndex = _candidates.indexWhere((c) => c.id == _mergeFrom);
    if (fromIndex == -1) {
      setState(() => _mergeFrom = null);
      return;
    }
    final from = _candidates[fromIndex];
    setState(() {
      target.ingredients.addAll(from.ingredients);
      target.steps.addAll(from.steps);
      target.tips = {...target.tips, ...from.tips}.toList();
      target.variants = {...target.variants, ...from.variants}.toList();
      target.allergens = {...target.allergens, ...from.allergens}.toList();
      if (from.startSec != null) {
        target.startSec = target.startSec == null
            ? from.startSec
            : (target.startSec! < from.startSec! ? target.startSec : from.startSec);
      }
      if (from.endSec != null) {
        target.endSec = target.endSec == null
            ? from.endSec
            : (target.endSec! > from.endSec! ? target.endSec : from.endSec);
      }
      _candidates.remove(from);
      _mergeFrom = null;
    });
  }

  void _snack(String m) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  @override
  Widget build(BuildContext context) {
    final selectedCount = _candidates.where((c) => c.selected).length;
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
                const Text(
                    "Lien YouTube / Instagram / TikTok / Facebook. L'IA extrait une ou plusieurs recettes.",
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

        // --- Detected recipes ----------------------------------------------
        if (_candidates.isNotEmpty) ...[
          const SizedBox(height: 13),
          Text(
            'Nous avons détecté ${_candidates.length} recette${_candidates.length > 1 ? 's' : ''}',
            style: const TextStyle(fontFamily: 'Newsreader', fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 2),
          const Text(
            "Quantités et découpage estimés par l'IA — vérifiez avant d'enregistrer.",
            style: TextStyle(fontSize: 12, color: kWarn),
          ),
          for (var i = 0; i < _candidates.length; i++)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: _candidateCard(_candidates[i], i),
            ),
          const SizedBox(height: 10),
          Row(children: [
            Checkbox(
              value: _candidates.isNotEmpty && _candidates.every((c) => c.selected),
              onChanged: (_) => _toggleSelectAll(),
            ),
            const Text('Tout (dé)sélectionner', style: TextStyle(fontSize: 13)),
          ]),
          SizedBox(
            width: double.infinity,
            child: GradientButton(
              label: 'Enregistrer $selectedCount sélectionnée${selectedCount > 1 ? 's' : ''}',
              onPressed: (_saving || selectedCount == 0) ? null : _save,
              expand: true,
              loading: _saving,
            ),
          ),
        ],
        // Outside the `_candidates.isNotEmpty` block on purpose: every
        // candidate defaults to selected, so a normal "Enregistrer" save-all
        // empties `_candidates` in the very setState that also sets
        // `_savedInfo` — if this banner were still nested inside that block
        // it would never paint on the common path, only after a partial
        // save that leaves cards behind.
        if (_savedInfo != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(_savedInfo!, style: const TextStyle(color: kGood)),
          ),
      ],
    );
  }

  /// One recipe card: collapsed = name + chips (portions / ingredient count /
  /// video time range); expanded = editable name, portions, ingredient rows
  /// and steps. Delete/merge/select act on this card regardless of whether
  /// it's expanded.
  Widget _candidateCard(_Candidate c, int index) {
    final title = c.name.trim().isEmpty ? 'Recette ${index + 1}' : c.name;
    final isMergeSource = _mergeFrom == c.id;
    final chips = <Widget>[
      if (c.yieldQty != null) importPill('${plainNumber(c.yieldQty)} portions', const Color(0xFFE3ECDB)),
      importPill('${c.ingredients.length} ingrédient${c.ingredients.length > 1 ? 's' : ''}',
          const Color(0xFFF3ECE0)),
      if (c.startSec != null) importPill(_timeChip(c), const Color(0xFFECE4D4)),
    ];

    return MockCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Checkbox(value: c.selected, onChanged: (_) => setState(() => c.selected = !c.selected)),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(
                            fontFamily: 'Newsreader', fontSize: 15, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Wrap(spacing: 6, runSpacing: 4, children: chips),
                  ],
                ),
              ),
              IconButton(
                onPressed: _candidates.length < 2 ? null : () => _onMergeTap(c),
                icon: Icon(Icons.call_merge, size: 20, color: isMergeSource ? kWarn : kMuted),
                tooltip: 'Fusionner',
              ),
              IconButton(
                onPressed: () => _deleteCandidate(c.id),
                icon: const Icon(Icons.delete_outline, size: 20, color: kMuted),
                tooltip: 'Supprimer cette recette',
              ),
              IconButton(
                onPressed: () => setState(() => c.expanded = !c.expanded),
                icon: Icon(c.expanded ? Icons.expand_less : Icons.expand_more, size: 22),
                tooltip: c.expanded ? 'Réduire' : 'Éditer',
              ),
            ],
          ),
          if (c.expanded) ..._candidateEditor(c),
        ],
      ),
    );
  }

  List<Widget> _candidateEditor(_Candidate c) {
    return [
      const Divider(height: 22),
      TextFormField(
        key: ValueKey('cand-name-${c.id}'),
        initialValue: c.name,
        decoration: const InputDecoration(labelText: 'Nom'),
        onChanged: (v) => setState(() => c.name = v),
      ),
      const SizedBox(height: 8),
      TextFormField(
        key: ValueKey('cand-portions-${c.id}'),
        initialValue: plainNumber(c.yieldQty),
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Portions'),
        onChanged: (v) =>
            c.yieldQty = v.trim().isEmpty ? null : double.tryParse(v.trim().replaceAll(',', '.')),
      ),
      const SizedBox(height: 12),
      const Text('Ingrédients', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
      ...c.ingredients.asMap().entries.map((e) {
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
                  decoration:
                      const InputDecoration(isDense: true, border: InputBorder.none, hintText: 'Qté'),
                  onChanged: (v) => ing.qty = v,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: TextFormField(
                  initialValue: ing.unit,
                  style: const TextStyle(fontSize: 13),
                  decoration:
                      const InputDecoration(isDense: true, border: InputBorder.none, hintText: 'unité'),
                  onChanged: (v) => ing.unit = v,
                ),
              ),
              InkWell(
                onTap: () => setState(() => c.ingredients.removeAt(i)),
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
          onPressed: () => setState(() => c.ingredients.add(_Ing('', '', ''))),
          icon: const Icon(Icons.add, size: 18),
          label: const Text('Ajouter un ingrédient'),
        ),
      ),
      const SizedBox(height: 12),
      const Text('Étapes', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
      const Text('Une étape par ligne', style: TextStyle(fontSize: 11.5, color: kMuted)),
      const SizedBox(height: 6),
      TextFormField(
        key: ValueKey('cand-steps-${c.id}'),
        initialValue: c.steps.join('\n'),
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
        onChanged: (v) => c.steps = v.split('\n'),
      ),
    ];
  }

  /// mm:ss (or "mm:ss–mm:ss") chip for the segment of the source video this
  /// recipe was detected in.
  String _timeChip(_Candidate c) {
    String fmt(double s) {
      final total = s.floor();
      final m = total ~/ 60;
      final sec = total % 60;
      return '$m:${sec.toString().padLeft(2, '0')}';
    }

    final start = fmt(c.startSec!);
    return c.endSec == null ? start : '$start–${fmt(c.endSec!)}';
  }
}
