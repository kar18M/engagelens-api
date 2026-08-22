/// core/router.dart
/// =================
/// GoRouter with role-based redirect guards.
library;


import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_provider.dart';
import '../screens/login_screen.dart';
import '../screens/teacher/teacher_home.dart';
import '../screens/teacher/live_scan_screen.dart';
import '../screens/teacher/batch_scan_screen.dart';
import '../screens/teacher/attendance_log_screen.dart';
import '../screens/teacher/enroll_screen.dart';
import '../screens/teacher/alerts_screen.dart';
import '../screens/teacher/override_screen.dart';
import '../screens/student/student_home.dart';
import '../screens/student/dashboard_screen.dart';
import '../screens/student/history_screen.dart';
import '../screens/student/profile_screen.dart';
import '../screens/admin/admin_home.dart';
import '../screens/admin/user_management_screen.dart';
import '../screens/admin/class_management_screen.dart';
import '../screens/admin/system_health_screen.dart';
import '../screens/admin/audit_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isAuth = authState.isAuthenticated;
      final isLoginPage = state.matchedLocation == '/login';

      if (!isAuth && !isLoginPage) return '/login';
      if (isAuth && isLoginPage) {
        // Route to the correct portal based on role
        switch (authState.role) {
          case 'teacher':
            return '/teacher';
          case 'student':
            return '/student';
          case 'admin':
            return '/admin';
          default:
            return '/login';
        }
      }
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),

      // ── Teacher routes ────────────────────────────────────────────────────────
      ShellRoute(
        builder: (context, state, child) => TeacherHome(child: child),
        routes: [
          GoRoute(path: '/teacher', builder: (_, __) => const AttendanceLogScreen()),
          GoRoute(path: '/teacher/live-scan', builder: (_, __) => const LiveScanScreen()),
          GoRoute(path: '/teacher/batch-scan', builder: (_, __) => const BatchScanScreen()),
          GoRoute(path: '/teacher/attendance-log', builder: (_, __) => const AttendanceLogScreen()),
          GoRoute(path: '/teacher/enroll', builder: (_, __) => const EnrollScreen()),
          GoRoute(path: '/teacher/alerts', builder: (_, __) => const AlertsScreen()),
          GoRoute(path: '/teacher/override', builder: (_, __) => const OverrideScreen()),
        ],
      ),

      // ── Student routes ────────────────────────────────────────────────────────
      ShellRoute(
        builder: (context, state, child) => StudentHome(child: child),
        routes: [
          GoRoute(path: '/student', builder: (_, __) => const DashboardScreen()),
          GoRoute(path: '/student/dashboard', builder: (_, __) => const DashboardScreen()),
          GoRoute(path: '/student/history', builder: (_, __) => const HistoryScreen()),
          GoRoute(path: '/student/profile', builder: (_, __) => const ProfileScreen()),
        ],
      ),

      // ── Admin routes ──────────────────────────────────────────────────────────
      ShellRoute(
        builder: (context, state, child) => AdminHome(child: child),
        routes: [
          GoRoute(path: '/admin', builder: (_, __) => const UserManagementScreen()),
          GoRoute(path: '/admin/users', builder: (_, __) => const UserManagementScreen()),
          GoRoute(path: '/admin/classes', builder: (_, __) => const ClassManagementScreen()),
          GoRoute(path: '/admin/health', builder: (_, __) => const SystemHealthScreen()),
          GoRoute(path: '/admin/audit', builder: (_, __) => const AuditScreen()),
        ],
      ),
    ],
  );
});
