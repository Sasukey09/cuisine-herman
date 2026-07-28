import 'package:flutter/material.dart';

import '../../main.dart' show kMuted, kSerif;

/// Widgets KPI partagés entre l'accueil (`dashboard_screen.dart`) et l'écran
/// « Pilotage Achats » (`pilotage_screen.dart`). Anciennement privés à
/// `dashboard_screen.dart` (`_Stat`, `_MiniStat`, `_SectionCard`), déplacés ici
/// tels quels et rendus publics dès qu'un second écran en a eu besoin.

/// Tuile de statistique. Deux traitements fidèles au design :
///  • dégradé (métriques « argent à risque ») — grand chiffre serif blanc, la
///    couleur du dégradé porte le signal (teal calme / rouge / ambre) ;
///  • carte crème (métriques de mouvement) — chiffre serif encre + sous-légende
///    à couleur sémantique (vert/rouge).
class KpiStat extends StatelessWidget {
  const KpiStat({
    super.key,
    required this.label,
    required this.value,
    required this.sub,
    this.subColor,
    this.gradient,
  });
  final String label, value, sub;
  final Color? subColor;
  final Gradient? gradient;

  @override
  Widget build(BuildContext context) {
    final onGrad = gradient != null;
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: gradient,
        color: onGrad ? null : theme.cardColor,
        border: onGrad ? null : Border.all(color: theme.dividerColor),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11.5,
              color: onGrad ? Colors.white.withValues(alpha: .85) : kMuted,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: kSerif.copyWith(
              fontSize: 25,
              fontWeight: FontWeight.w700,
              color: onGrad ? Colors.white : theme.colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            sub,
            style: TextStyle(
              fontSize: 11,
              color: onGrad ? Colors.white.withValues(alpha: .9) : (subColor ?? kMuted),
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

/// Tuile de synthèse compacte (3 par ligne). Grand chiffre serif blanc sur
/// dégradé ; [FittedBox] pour ne jamais déborder sur les gros montants.
class KpiMiniStat extends StatelessWidget {
  const KpiMiniStat({super.key, required this.label, required this.value, required this.gradient});
  final String label, value;
  final Gradient gradient;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(gradient: gradient, borderRadius: BorderRadius.circular(14)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value,
                style: kSerif.copyWith(
                    fontSize: 21, fontWeight: FontWeight.w700, color: Colors.white)),
          ),
          const SizedBox(height: 4),
          Text(label,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: 10.5,
                  height: 1.15,
                  color: Colors.white.withValues(alpha: .9),
                  fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

/// Carte de section : icône + titre, puis un contenu libre.
class KpiSectionCard extends StatelessWidget {
  const KpiSectionCard({
    super.key,
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.child,
  });
  final String icon, title;
  final Color iconColor;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: theme.cardColor,
        border: Border.all(color: theme.dividerColor),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(icon, style: TextStyle(color: iconColor, fontSize: 13)),
            const SizedBox(width: 7),
            Text(title, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }
}
