/// screens/admin/system_health_screen.dart
library;

import 'package:flutter/material.dart';
import '../../core/api_client.dart';

class SystemHealthScreen extends StatefulWidget {
  const SystemHealthScreen({super.key});
  @override
  State<SystemHealthScreen> createState() => _SystemHealthScreenState();
}

class _SystemHealthScreenState extends State<SystemHealthScreen> {
  Map<String, dynamic>? _health;
  bool _loading = false;
  final _api = ApiClient();

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await _api.get('/admin/health');
      setState(() => _health = resp.data as Map<String, dynamic>);
    } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
    finally { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_health == null) return Center(child: ElevatedButton(onPressed: _load, child: const Text('Retry')));

    final mongo = _health!['mongodb'] as Map<String, dynamic>? ?? {};
    final cpu = _health!['cpu_percent'];
    final mem = _health!['memory'] as Map<String, dynamic>?;
    final disk = _health!['disk'] as Map<String, dynamic>?;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('System Health', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: cs.primary)),
              const Spacer(),
              IconButton(onPressed: _load, icon: Icon(Icons.refresh, color: cs.primary)),
            ],
          ),
          const SizedBox(height: 12),
          // MongoDB
          _sectionCard('MongoDB', [
            _infoRow('Status', mongo['status'] as String? ?? '-', cs),
            _infoRow('Students enrolled', '${mongo['students_enrolled'] ?? '-'}', cs),
            _infoRow('Attendance records', '${mongo['attendance_records'] ?? '-'}', cs),
          ], cs),
          const SizedBox(height: 12),
          // System
          _sectionCard('System', [
            _infoRow('CPU', '${cpu ?? '-'}%', cs),
            if (mem != null) _infoRow('Memory', '${mem['used_gb']} / ${mem['total_gb']} GB (${mem['percent']}%)', cs),
            if (disk != null) _infoRow('Disk', '${disk['used_gb']} / ${disk['total_gb']} GB (${disk['percent']}%)', cs),
          ], cs),
        ],
      ),
    );
  }

  Widget _sectionCard(String title, List<Widget> children, ColorScheme cs) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 8),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value, ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: cs.onSurface.withOpacity(0.6))),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
