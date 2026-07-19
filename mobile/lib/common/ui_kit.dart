import 'package:flutter/material.dart';

import '../main.dart';

/// Primitives d'interface FoodGad — fidèles au design Claude Design.
///
/// Composants réutilisables partagés par tous les écrans : bouton dégradé,
/// tuiles de statistiques, barre de food cost, pastilles de statut et chips de
/// catégorie. Centraliser ces briques garde l'app visuellement homogène
/// (mêmes rayons, dégradés, ombres et typographies que la référence).

/// Titre serif de section/écran (Newsreader), aligné sur les `<h1>` du design.
class SerifTitle extends StatelessWidget {
  const SerifTitle(this.text, {super.key, this.size = 26, this.color});
  final String text;
  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: kSerif.copyWith(
        fontSize: size,
        fontWeight: FontWeight.w600,
        color: color ?? Theme.of(context).colorScheme.onSurface,
      ),
    );
  }
}

/// Bouton d'action principal : dégradé terracotta + lueur (CTA du design).
class GradientButton extends StatelessWidget {
  const GradientButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.gradient = kGradTerracotta,
    this.expand = false,
    this.loading = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final Gradient gradient;
  final bool expand;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null || loading;
    final child = Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      decoration: BoxDecoration(
        gradient: disabled ? null : gradient,
        color: disabled ? kMuted.withValues(alpha: .35) : null,
        borderRadius: BorderRadius.circular(10),
        boxShadow: disabled ? null : kGlow,
      ),
      child: Row(
        mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (loading)
            const SizedBox(
              height: 16,
              width: 16,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
            )
          else if (icon != null)
            Icon(icon, size: 18, color: Colors.white),
          if ((loading || icon != null)) const SizedBox(width: 8),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: disabled ? null : onPressed,
        borderRadius: BorderRadius.circular(10),
        child: child,
      ),
    );
  }
}

/// FAB à dégradé terracotta + lueur (CTA flottant du design), en remplacement
/// du [FloatingActionButton] Material plein.
class GradientFab extends StatelessWidget {
  const GradientFab({
    super.key,
    required this.onPressed,
    this.icon = Icons.add,
    this.gradient = kGradTerracotta,
  });

  final VoidCallback? onPressed;
  final IconData icon;
  final Gradient gradient;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(16),
        boxShadow: kGlow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(16),
          child: SizedBox(
            width: 56,
            height: 56,
            child: Icon(icon, color: Colors.white, size: 26),
          ),
        ),
      ),
    );
  }
}

/// Tuile de statistique à dégradé (Food cost moyen, Alertes prix…).
/// Grand chiffre en serif blanc sur fond dégradé, comme le dashboard du design.
class StatTile extends StatelessWidget {
  const StatTile({
    super.key,
    required this.label,
    required this.value,
    this.gradient = kGradTeal,
    this.onTap,
  });

  final String label;
  final String value;
  final Gradient gradient;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: gradient,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 11.5,
                  color: Colors.white.withValues(alpha: .85),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                value,
                style: kSerif.copyWith(
                  fontSize: 30,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Petite tuile d'icône à dégradé (en-tête des cartes stat du design web).
class GradientIconTile extends StatelessWidget {
  const GradientIconTile({super.key, required this.icon, this.gradient = kGradAmber, this.size = 38});
  final IconData icon;
  final Gradient gradient;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Icon(icon, size: size * .45, color: Colors.white),
    );
  }
}

/// Barre de food cost : piste beige + remplissage proportionnel au pourcentage.
class FoodCostBar extends StatelessWidget {
  const FoodCostBar({super.key, required this.percent, this.color, this.height = 6});

  /// Pourcentage 0–100.
  final double percent;
  final Color? color;
  final double height;

  @override
  Widget build(BuildContext context) {
    final p = percent.clamp(0, 100) / 100.0;
    // Couleur par défaut : vert < 25 %, ambre < 33 %, rouge au-delà.
    final fill = color ?? (percent >= 33 ? kBad : (percent >= 25 ? kWarn : kSuccess));
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: Stack(
        children: [
          Container(height: height, color: const Color(0xFFE9DFCA)),
          FractionallySizedBox(
            widthFactor: p.toDouble(),
            child: Container(height: height, color: fill),
          ),
        ],
      ),
    );
  }
}

/// Pastille de statut arrondie (Traité / En attente / Erreur…).
class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.label, required this.color, this.background});
  final String label;
  final Color color;
  final Color? background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: background ?? color.withValues(alpha: .15),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: color),
      ),
    );
  }
}

/// Chip de catégorie produit (pastille colorée + libellé).
class CategoryChip extends StatelessWidget {
  const CategoryChip({super.key, required this.category});
  final String category;

  @override
  Widget build(BuildContext context) {
    final color = kCategoryColors[category] ?? kMuted;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(
          category,
          style: const TextStyle(fontSize: 12.5, color: kMuted, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}
