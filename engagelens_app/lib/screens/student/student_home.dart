/// screens/student/student_home.dart
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/auth_provider.dart';

class StudentHome extends ConsumerStatefulWidget {
  final Widget child;
  const StudentHome({super.key, required this.child});
  @override
  ConsumerState<StudentHome> createState() => _StudentHomeState();
}

class _StudentHomeState extends ConsumerState<StudentHome> {
  int _idx = 0;
  final _routes = ['/student/dashboard', '/student/history', '/student/profile'];

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.school, color: cs.secondary, size: 22),
          const SizedBox(width: 8),
          Text(auth.fullName ?? 'Student Portal'),
        ]),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authProvider.notifier).logout(),
            tooltip: 'Sign Out',
          ),
        ],
      ),
      body: widget.child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _idx,
        backgroundColor: const Color(0xFF1A1A2E),
        indicatorColor: cs.secondary.withOpacity(0.2),
        onDestinationSelected: (i) {
          setState(() => _idx = i);
          context.go(_routes[i]);
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: 'Dashboard'),
          NavigationDestination(icon: Icon(Icons.history_outlined), selectedIcon: Icon(Icons.history), label: 'History'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}
