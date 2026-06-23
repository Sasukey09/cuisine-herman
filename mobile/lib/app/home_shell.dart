import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../main.dart' show kSerif, kMuted, kTerracotta, kCard, kBorder, kSecondary;
import '../features/admin/admin_screen.dart';
import '../features/assistant/assistant_screen.dart';
import '../features/auth/auth_controller.dart';
import '../features/custom_fields/custom_fields_screen.dart';
import '../features/dashboard/dashboard_screen.dart';
import '../features/invoices/invoices_screen.dart';
import '../features/metrics/metrics_screen.dart';
import '../features/prix/price_screen.dart';
import '../features/products/products_screen.dart';
import '../features/recipes/recipes_screen.dart';
import '../features/reports/reports_screen.dart';
import '../features/suppliers/suppliers_screen.dart';
import '../features/video/video_import_screen.dart';

class _Mod {
  const _Mod(this.id, this.title, this.subtitle, this.icon, this.screen,
      {this.adminOnly = false});
  final String id;
  final String title;
  final String subtitle;
  final IconData icon;
  final Widget screen;
  final bool adminOnly;
}

// Order matters: the first 4 are the bottom-bar primary tabs.
const _modules = <_Mod>[
  _Mod('dashboard', 'Bonjour, Chef', "Vos coûts aujourd'hui",
      Icons.grid_view_outlined, DashboardScreen()),
  _Mod('produits', 'Produits', 'Catalogue et coûts',
      Icons.inventory_2_outlined, ProductsScreen()),
  _Mod('factures', 'Factures', 'Import & OCR',
      Icons.receipt_long_outlined, InvoicesScreen()),
  _Mod('recettes', 'Recettes', 'Coût matière & marge',
      Icons.restaurant_menu_outlined, RecipesScreen()),
  // Secondary modules (shown in the "Plus" sheet).
  _Mod('fournisseurs', 'Fournisseurs', 'Partenaires & catalogues',
      Icons.local_shipping_outlined, SuppliersScreen()),
  _Mod('prix', 'Variations de prix', 'Évolution des coûts',
      Icons.trending_up, PriceScreen()),
  _Mod('import', 'Import vidéo', 'Extraire une recette',
      Icons.movie_outlined, VideoImportScreen()),
  _Mod('assistant', 'Assistant IA', 'Posez vos questions',
      Icons.smart_toy_outlined, AssistantScreen()),
  _Mod('indicateurs', 'Indicateurs', 'Formules & ratios',
      Icons.calculate_outlined, MetricsScreen()),
  _Mod('champs', 'Champs perso', 'Vos attributs',
      Icons.tune_outlined, CustomFieldsScreen()),
  _Mod('rapports', 'Rapports', 'Exports & analyses',
      Icons.table_chart_outlined, ReportsScreen()),
  _Mod('administration', 'Administration', 'Utilisateurs & rôles',
      Icons.admin_panel_settings_outlined, AdminScreen(), adminOnly: true),
];

const _primaryCount = 4; // dashboard, produits, factures, recettes

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _index = 0; // index into _modules

  String _initials(Map<String, dynamic>? user) {
    final name = (user?['name'] as String?)?.trim();
    final base = (name != null && name.isNotEmpty) ? name : (user?['email'] as String? ?? '?');
    final t = base.trim();
    return t.substring(0, t.length >= 2 ? 2 : 1).toUpperCase();
  }

  void _openMore() {
    final auth = ref.read(authControllerProvider);
    final isAdmin =
        ((auth.user?['roles'] as List?)?.cast<String>() ?? const []).contains('admin');
    final mods = _modules
        .skip(_primaryCount)
        .where((m) => !m.adminOnly || isAdmin)
        .toList();
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFFF4EFE6),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 26),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 42,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFD6CDBD),
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
              ),
              const Padding(
                padding: EdgeInsets.only(left: 4, bottom: 12),
                child: Text('Tous les modules',
                    style: TextStyle(
                        fontFamily: 'serif', fontSize: 19, fontWeight: FontWeight.w600)),
              ),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                childAspectRatio: 2.4,
                children: [
                  for (final m in mods)
                    InkWell(
                      borderRadius: BorderRadius.circular(14),
                      onTap: () {
                        Navigator.of(ctx).pop();
                        setState(() => _index = _modules.indexOf(m));
                      },
                      child: Container(
                        padding: const EdgeInsets.all(13),
                        decoration: BoxDecoration(
                          color: kCard,
                          border: Border.all(color: kBorder),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(m.icon, color: kTerracotta, size: 22),
                            const SizedBox(height: 8),
                            Text(m.title,
                                style: const TextStyle(
                                    fontSize: 13, fontWeight: FontWeight.w600)),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _onTab(int i) {
    if (i < _primaryCount) {
      setState(() => _index = i);
    } else {
      _openMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);
    final current = _modules[_index];
    final onPrimary = _index < _primaryCount;
    final navIndex = onPrimary ? _index : _primaryCount; // highlight "Plus" otherwise

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // Header (serif title + subtitle + avatar)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 16, 12),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(current.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: kSerif.copyWith(fontSize: 24)),
                        const SizedBox(height: 2),
                        Text(current.subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 12.5, color: kMuted)),
                      ],
                    ),
                  ),
                  PopupMenuButton<String>(
                    tooltip: 'Compte',
                    onSelected: (v) {
                      if (v == 'logout') {
                        ref.read(authControllerProvider.notifier).logout();
                      }
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'logout', child: Text('Déconnexion')),
                    ],
                    child: CircleAvatar(
                      radius: 19,
                      backgroundColor: kTerracotta,
                      child: Text(_initials(auth.user),
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 13,
                              fontWeight: FontWeight.w600)),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: IndexedStack(
                index: _index,
                children: _modules.map((m) => m.screen).toList(),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: navIndex,
        onDestinationSelected: _onTab,
        height: 66,
        backgroundColor: kCard,
        indicatorColor: kSecondary,
        surfaceTintColor: Colors.transparent,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: const [
          NavigationDestination(icon: Icon(Icons.grid_view_outlined), label: 'Accueil'),
          NavigationDestination(icon: Icon(Icons.inventory_2_outlined), label: 'Produits'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label: 'Factures'),
          NavigationDestination(icon: Icon(Icons.restaurant_menu_outlined), label: 'Recettes'),
          NavigationDestination(icon: Icon(Icons.apps_outlined), label: 'Plus'),
        ],
      ),
    );
  }
}
