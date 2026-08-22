/// screens/admin/user_management_screen.dart
library;

import 'package:flutter/material.dart';
import '../../core/api_client.dart';

class UserManagementScreen extends StatefulWidget {
  const UserManagementScreen({super.key});
  @override
  State<UserManagementScreen> createState() => _UserManagementScreenState();
}

class _UserManagementScreenState extends State<UserManagementScreen> {
  List<Map<String, dynamic>> _users = [];
  bool _loading = false;
  final _api = ApiClient();

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await _api.get('/admin/users');
      setState(() => _users = (resp.data as List).cast<Map<String, dynamic>>());
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    const roleColors = {'admin': Color(0xFFFFB347), 'teacher': Color(0xFF6C63FF), 'student': Color(0xFF48C6EF)};

    return _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: _users.length,
            separatorBuilder: (_, __) => const SizedBox(height: 4),
            itemBuilder: (_, i) {
              final u = _users[i];
              final role = u['role'] as String;
              final color = roleColors[role] ?? cs.primary;
              final isActive = (u['is_active'] as bool?) ?? true;
              return Card(
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: color.withOpacity(0.15),
                    child: Text((u['full_name'] as String? ?? 'U')[0].toUpperCase(), style: TextStyle(color: color)),
                  ),
                  title: Text(u['full_name'] as String? ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text('@${u['username'] ?? ''}'),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(6)),
                        child: Text(role, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
                      ),
                      const SizedBox(width: 6),
                      Icon(isActive ? Icons.circle : Icons.circle, size: 10, color: isActive ? Colors.green : Colors.grey),
                    ],
                  ),
                ),
              );
            },
          );
  }
}
