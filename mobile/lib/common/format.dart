import 'package:flutter/material.dart';

import '../main.dart' show kCard, kBorder, kBad, kGood;

/// French euro formatting: 8.51 -> "8,51 €" ; null -> "—".
String eur(num? v) {
  if (v == null) return '—';
  return '${v.toStringAsFixed(2).replaceAll('.', ',')} €';
}

/// Signed percent like the mockup: 18.2 -> "+18,2 %" ; -14 -> "−14,0 %".
String pctSigned(num? v) {
  if (v == null) return '';
  final a = v.abs().toStringAsFixed(1).replaceAll('.', ',');
  return '${v < 0 ? '−' : '+'}$a %';
}

/// Rounded percent: 76.0 -> "76 %".
String pctRound(num? v) => v == null ? '—' : '${v.round()} %';

/// Pill badge: red for a rise, green for a drop (matches the mockup).
class TrendBadge extends StatelessWidget {
  const TrendBadge(this.pct, {super.key});
  final num? pct;

  @override
  Widget build(BuildContext context) {
    if (pct == null || pct == 0) return const SizedBox.shrink();
    final up = pct! > 0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: up ? const Color(0xFFF6E1DC) : const Color(0xFFE3ECDB),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(pctSigned(pct),
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: up ? kBad : kGood)),
    );
  }
}

/// Cream card with the mockup's border + radius.
class MockCard extends StatelessWidget {
  const MockCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.fromLTRB(15, 13, 15, 13),
    this.onTap,
  });
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final card = Container(
      decoration: BoxDecoration(
        color: kCard,
        border: Border.all(color: kBorder),
        borderRadius: BorderRadius.circular(13),
      ),
      padding: padding,
      child: child,
    );
    if (onTap == null) return card;
    return InkWell(borderRadius: BorderRadius.circular(13), onTap: onTap, child: card);
  }
}
