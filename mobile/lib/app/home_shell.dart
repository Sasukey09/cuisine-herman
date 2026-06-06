import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/admin/admin_screen.dart';
import '../features/assistant/assistant_screen.dart';
import '../features/auth/auth_controller.dart';
import '../features/custom_fields/custom_fields_screen.dart';
import '../features/dashboard/dashboard_screen.dart';
import '../features/invoices/invoices_screen.dart';
import '../features/metrics/metrics_screen.dart';
import '../features/products/products_screen.dart';
import '../features/recipes/recipes_screen.dart';
import '../features/reports/reports_screen.dart';
import '../features/suppliers/suppliers_screen.dart';
import '../features/video/video_import_screen.dart';

class _Section {
  const _Section(this.title, this.icon, this.screen, {this.adminOnly = false});
  final String title;
  final IconData icon;
  final Widget screen;
  final bool adminOnly;
}

const _allSections = <_Section>[
  _Section('Tableau de bord', Icons.dashboard_outlined, DashboardScreen()),
  _Section('Produits', Icons.inventory_2_outlined, ProductsScreen()),
  _Section('Fournisseurs', Icons.local_shipping_outlined, SuppliersScreen()),
  _Section('Factures', Icons.receipt_long_outlined, InvoicesScreen()),
  _Section('Recettes', Icons.menu_book_outlined, RecipesScreen()),
  _Section('Import vidéo', Icons.video_library_outlined, VideoImportScreen()),
  _Section('Assistant IA', Icons.smart_toy_outlined, AssistantScreen()),
  _Section('Indicateurs', Icons.calculate_outlined, MetricsScreen()),
  _Section('Champs perso', Icons.tune_outlined, CustomFieldsScreen()),
  _Section('Rapports', Icons.table_chart_outlined, ReportsScreen()),
  _Section('Administration', Icons.admin_panel_settings_outlined, AdminScreen(), adminOnly: true),
];

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);
    final roles = (auth.user?['roles'] as List?)?.cast<String>() ?? const [];
    final isAdmin = roles.contains('admin');
    final sections =
        _allSections.where((s) => !s.adminOnly || isAdmin).toList();
    if (_index >= sections.length) _index = 0;
    final current = sections[_index];

    return Scaffold(
      appBar: AppBar(title: Text(current.title)),
      drawer: Drawer(
        child: SafeArea(
          child: Column(
            children: [
              DrawerHeader(
                decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary),
                child: Align(
                  alignment: Alignment.bottomLeft,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Cuisine Herman',
                          style: TextStyle(
                              color: Theme.of(context).colorScheme.onPrimary,
                              fontSize: 20,
                              fontWeight: FontWeight.bold)),
                      Text('${auth.user?['email'] ?? ''}',
                          style: TextStyle(
                              color: Theme.of(context).colorScheme.onPrimary.withValues(alpha: 0.85),
                              fontSize: 12)),
                    ],
                  ),
                ),
              ),
              Expanded(
                child: ListView.builder(
                  padding: EdgeInsets.zero,
                  itemCount: sections.length,
                  itemBuilder: (context, i) {
                    final s = sections[i];
                    return ListTile(
                      leading: Icon(s.icon),
                      title: Text(s.title),
                      selected: i == _index,
                      onTap: () {
                        setState(() => _index = i);
                        Navigator.of(context).pop();
                      },
                    );
                  },
                ),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.logout),
                title: const Text('Déconnexion'),
                onTap: () => ref.read(authControllerProvider.notifier).logout(),
              ),
            ],
          ),
        ),
      ),
      body: IndexedStack(
        index: _index,
        children: sections.map((s) => s.screen).toList(),
      ),
    );
  }
}
