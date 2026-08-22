/// screens/admin/admin_home.dart
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/auth_provider.dart';

class AdminHome extends ConsumerStatefulWidget {
  final Widget child;
  const AdminHome({super.key, required this.child});
  @override
  ConsumerState<AdminHome> createState() => _AdminHomeState();
}

class _AdminHomeState extends ConsumerState<AdminHome> {
  int _idx = 0;
  final _routes = ['/admin/users', '/admin/classes', '/admin/health', '/admin/audit'];

  @override
  Widget build(BuildContext context) {
    const adminColor = Color(0xFFFFB347); // Amber

    return Scaffold(
      appBar: AppBar(
        title: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.admin_panel_settings, color: adminColor, size: 22),
          const SizedBox(width: 8),
          const Text('Admin Panel'),
        ]),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authProvider.notifier).logout(),
          ),
        ],
      ),
      body: widget.child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _idx,
        backgroundColor: const Color(0xFF1A1A2E),
        indicatorColor: adminColor.withOpacity(0.2),
        onDestinationSelected: (i) {
          setState(() => _idx = i);
          context.go(_routes[i]);
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.manage_accounts_outlined), selectedIcon: Icon(Icons.manage_accounts), label: 'Users'),
          NavigationDestination(icon: Icon(Icons.class_outlined), selectedIcon: Icon(Icons.class_), label: 'Classes'),
          NavigationDestination(icon: Icon(Icons.monitor_heart_outlined), selectedIcon: Icon(Icons.monitor_heart), label: 'Health'),
          NavigationDestination(icon: Icon(Icons.history_edu_outlined), selectedIcon: Icon(Icons.history_edu), label: 'Audit'),
        ],
      ),
    );
  }
}
