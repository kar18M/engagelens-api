/// screens/admin/audit_screen.dart
library;

import 'package:flutter/material.dart';
import '../../core/api_client.dart';

class AuditScreen extends StatefulWidget {
  const AuditScreen({super.key});
  @override
  State<AuditScreen> createState() => _AuditScreenState();
}

class _AuditScreenState extends State<AuditScreen> {
  List<Map<String, dynamic>> _logs = [];
  bool _loading = false;
  final _api = ApiClient();

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await _api.get('/admin/audit', params: {'limit': '50'});
      setState(() => _logs = (resp.data as List).cast<Map<String, dynamic>>());
    } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
    finally { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    if (_loading) return const Center(child: CircularProgressIndicator());
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: _logs.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (_, i) {
        final log = _logs[i];
        return ListTile(
          leading: Icon(Icons.history_edu, color: cs.primary, size: 20),
          title: Text(log['action'] as String? ?? '', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          subtitle: Text('by ${log['actor'] ?? '-'}  •  ${log['timestamp'] ?? ''}', style: const TextStyle(fontSize: 11)),
        );
      },
    );
  }
}
