/// screens/student/profile_screen.dart
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/auth_provider.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final cs = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const SizedBox(height: 20),
          CircleAvatar(
            radius: 52,
            backgroundColor: cs.primary.withOpacity(0.2),
            child: Text(
              (auth.fullName ?? 'S')[0].toUpperCase(),
              style: TextStyle(fontSize: 40, fontWeight: FontWeight.bold, color: cs.primary),
            ),
          ),
          const SizedBox(height: 16),
          Text(auth.fullName ?? '', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(color: cs.secondary.withOpacity(0.15), borderRadius: BorderRadius.circular(20)),
            child: Text('Student', style: TextStyle(color: cs.secondary, fontWeight: FontWeight.w600)),
          ),
          const SizedBox(height: 32),
          Card(
            child: Column(
              children: [
                _infoTile(Icons.badge_outlined, 'Username', auth.username ?? '-', cs),
                const Divider(height: 1),
                _infoTile(Icons.account_circle_outlined, 'Student ID', auth.linkedStudentId ?? 'Not linked', cs),
              ],
            ),
          ),
          const Spacer(),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: OutlinedButton.icon(
              onPressed: () => ref.read(authProvider.notifier).logout(),
              icon: const Icon(Icons.logout),
              label: const Text('Sign Out'),
              style: OutlinedButton.styleFrom(
                foregroundColor: cs.error,
                side: BorderSide(color: cs.error.withOpacity(0.5)),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _infoTile(IconData icon, String label, String value, ColorScheme cs) {
    return ListTile(
      leading: Icon(icon, color: cs.primary),
      title: Text(label, style: TextStyle(fontSize: 12, color: cs.onSurface.withOpacity(0.55))),
      subtitle: Text(value, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
    );
  }
}
