import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/home_shell.dart';
import 'core/theme_controller.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/login_screen.dart';

void main() {
  runApp(const ProviderScope(child: FoodGadApp()));
}

class FoodGadApp extends ConsumerWidget {
  const FoodGadApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Clair = rendu de référence ; dark chaud dérivé, activable via le réglage.
    final mode = ref.watch(themeModeProvider);
    return MaterialApp(
      title: 'FoodGad',
      debugShowCheckedModeBanner: false,
      theme: foodGadTheme(),
      darkTheme: foodGadTheme(brightness: Brightness.dark),
      themeMode: mode,
      home: const _AuthGate(),
    );
  }
}

// --- Palette éditoriale chaude (design FoodGad — Claude Design) -------------
// Surfaces claires
const kCream = Color(0xFFF4EFE6); // fond clair
const kCard = Color(0xFFFBF8F2); // cartes claires
const kBorder = Color(0xFFE6DCC8); // bords (aligné au design)
const kSecondary = Color(0xFFEFE7D8); // chips / entête de table
// Accents (identiques clair/sombre)
const kTerracotta = Color(0xFFC2632F); // primaire
const kSuccess = Color(0xFF059669); // succès (vert)
const kSidebar = Color(0xFF2A2422); // barre latérale sombre
// Texte
const kInk = Color(0xFF2A2620); // texte principal (clair)
const kMuted = Color(0xFF8A847A); // texte atténué
const kGood = Color(0xFF2F6F62); // variation à la baisse (teal/vert)
const kBad = Color(0xFFB23A2E); // variation à la hausse (rouge)
const kWarn = Color(0xFFB8763A); // ambre foncé
// Surfaces sombres (dark chaud dérivé)
const kInkDarkBg = Color(0xFF201C1A); // fond sombre
const kInkDarkCard = Color(0xFF2F2926); // cartes sombres
const kInkDarkBorder = Color(0xFF3A322E);
const kCreamOnDark = Color(0xFFF4EFE6); // texte clair sur sombre
const kMutedOnDark = Color(0xFFA89F90);

// --- Dégradés signature ----------------------------------------------------
const kGradTerracotta = LinearGradient(
  begin: Alignment.topLeft, end: Alignment.bottomRight,
  colors: [Color(0xFFD1703D), Color(0xFFA8532A)],
);
const kGradBrand = LinearGradient(
  begin: Alignment.topLeft, end: Alignment.bottomRight,
  colors: [Color(0xFFD98C5F), Color(0xFFC2632F)],
);
const kGradTeal = LinearGradient(
  begin: Alignment.topLeft, end: Alignment.bottomRight,
  colors: [Color(0xFF3C8A7A), Color(0xFF204D43)],
);
const kGradAmber = LinearGradient(
  begin: Alignment.topLeft, end: Alignment.bottomRight,
  colors: [Color(0xFFE0983F), Color(0xFFC2632F)],
);
const kGradDanger = LinearGradient(
  begin: Alignment.topLeft, end: Alignment.bottomRight,
  colors: [Color(0xFFC05A4A), Color(0xFF8A2E22)],
);

/// Lueur terracotta sous les boutons/tuiles primaires (design glow).
const List<BoxShadow> kGlow = [
  BoxShadow(color: Color(0x59C2632F), blurRadius: 12, offset: Offset(0, 4)),
];

/// Couleurs de famille produit (chips catégorie).
// The canonical product taxonomy — MUST mirror the backend classifier's
// CATEGORIES (app/services/classification/classifier.py). Order is the display
// order used by the picker and the filter chips.
const List<String> kProductCategories = <String>[
  'Viande',
  'Poisson',
  'Légumes',
  'Fruits',
  'Produits laitiers',
  'Boulangerie',
  'Épicerie',
  'Boissons',
  'Surgelés',
  'Desserts',
  'Condiments',
  'Hygiène',
  'Emballages',
  'Autres',
];

const Map<String, Color> kCategoryColors = {
  'Viande': Color(0xFFB23A2E),
  'Poisson': Color(0xFF2F6F62),
  'Légumes': Color(0xFF4A7C3F),
  'Fruits': Color(0xFFCB4E2A),
  'Produits laitiers': Color(0xFFD97706),
  'Boulangerie': Color(0xFFB08442),
  'Épicerie': Color(0xFF8A847A),
  'Boissons': Color(0xFF3E6DA3),
  'Surgelés': Color(0xFF5AA6C9),
  'Desserts': Color(0xFFC06C9E),
  'Condiments': Color(0xFF9A6A2F),
  'Hygiène': Color(0xFF6B8E9E),
  'Emballages': Color(0xFF8A7F70),
  'Autres': Color(0xFF9AA0A6),
};

ThemeData foodGadTheme({Brightness brightness = Brightness.light}) {
  final isDark = brightness == Brightness.dark;
  final bg = isDark ? kInkDarkBg : kCream;
  final card = isDark ? kInkDarkCard : kCard;
  final border = isDark ? kInkDarkBorder : kBorder;
  final ink = isDark ? kCreamOnDark : kInk;
  final muted = isDark ? kMutedOnDark : kMuted;

  final scheme = ColorScheme.fromSeed(
    seedColor: kTerracotta,
    brightness: brightness,
  ).copyWith(
    primary: kTerracotta,
    onPrimary: Colors.white,
    secondary: kSecondary,
    onSecondary: kInk,
    surface: bg,
    onSurface: ink,
    error: kBad,
    outline: border,
    outlineVariant: border,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    fontFamily: 'Public Sans',
    colorScheme: scheme,
    scaffoldBackgroundColor: bg,
    cardColor: card,
    appBarTheme: AppBarTheme(
      backgroundColor: bg,
      foregroundColor: ink,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: kTerracotta,
        foregroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        textStyle: const TextStyle(
            fontFamily: 'Public Sans', fontWeight: FontWeight.w600, fontSize: 14),
      ),
    ),
    // FAB terracotta plein + icône blanche (CTA du design, au lieu du conteneur
    // pâle Material 3 par défaut).
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: kTerracotta,
      foregroundColor: Colors.white,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: isDark ? kInkDarkBg : kCard,
      hintStyle: TextStyle(color: muted, fontSize: 13),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(11),
        borderSide: BorderSide(color: border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(11),
        borderSide: BorderSide(color: border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(11),
        borderSide: const BorderSide(color: kTerracotta),
      ),
    ),
    dividerColor: border,
  );
}

/// Style de titre serif (Newsreader — police du design). Sans couleur : hérite
/// de la couleur de texte du thème (encre en clair, crème en sombre) — les
/// usages sur fond coloré la surchargent via `copyWith(color: …)`.
const TextStyle kSerif = TextStyle(
  fontFamily: 'Newsreader',
  fontWeight: FontWeight.w600,
);

/// Switches between the login screen and the app shell based on auth status.
class _AuthGate extends ConsumerWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(authControllerProvider).status;
    switch (status) {
      case AuthStatus.unknown:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.authenticated:
        return const HomeShell();
      case AuthStatus.unauthenticated:
        return const LoginScreen();
    }
  }
}
