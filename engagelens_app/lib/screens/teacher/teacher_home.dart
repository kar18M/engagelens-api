/// screens/teacher/teacher_home.dart
/// ===================================
/// Bottom navigation shell for the teacher portal.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/auth_provider.dart';

class TeacherHome extends ConsumerStatefulWidget {
  final Widget child;
  const TeacherHome({super.key, required this.child});

  @override
  ConsumerState<TeacherHome> createState() => _TeacherHomeState();
}

class _TeacherHomeState extends ConsumerState<TeacherHome> {
  int _selectedIndex = 0;

  final _routes = const [
    '/teacher/attendance-log',
    '/teacher/live-scan',
    '/teacher/batch-scan',
    '/teacher/enroll',
    '/teacher/alerts',
  ];

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.face_retouching_natural, color: cs.primary, size: 24),
            const SizedBox(width: 8),
            const Text('EngageLens'),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: PopupMenuButton<String>(
              icon: CircleAvatar(
                backgroundColor: cs.primary.withOpacity(0.2),
                child: Text(
                  (auth.fullName ?? 'T')[0].toUpperCase(),
                  style: TextStyle(color: cs.primary, fontWeight: FontWeight.bold),
                ),
              ),
              itemBuilder: (_) => [
                PopupMenuItem(
                  value: 'name',
                  enabled: false,
                  child: Text(auth.fullName ?? 'Teacher', style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
                const PopupMenuItem(value: 'override', child: Text('Manual Override')),
                const PopupMenuDivider(),
                const PopupMenuItem(value: 'logout', child: Text('Sign Out')),
              ],
              onSelected: (v) {
                if (v == 'logout') ref.read(authProvider.notifier).logout();
                if (v == 'override') context.go('/teacher/override');
              },
            ),
          ),
        ],
      ),
      body: widget.child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        backgroundColor: const Color(0xFF1A1A2E),
        indicatorColor: cs.primary.withOpacity(0.2),
        onDestinationSelected: (i) {
          setState(() => _selectedIndex = i);
          context.go(_routes[i]);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.list_alt_outlined),
            selectedIcon: Icon(Icons.list_alt),
            label: 'Log',
          ),
          NavigationDestination(
            icon: Icon(Icons.videocam_outlined),
            selectedIcon: Icon(Icons.videocam),
            label: 'Live Scan',
          ),
          NavigationDestination(
            icon: Icon(Icons.grid_view_outlined),
            selectedIcon: Icon(Icons.grid_view),
            label: 'Batch',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_add_outlined),
            selectedIcon: Icon(Icons.person_add),
            label: 'Enroll',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications_outlined),
            selectedIcon: Icon(Icons.notifications),
            label: 'Alerts',
          ),
        ],
      ),
    );
  }
}
