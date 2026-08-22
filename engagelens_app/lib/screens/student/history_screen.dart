/// screens/student/history_screen.dart
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/auth_provider.dart';
import '../../models/attendance.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});
  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  List<AttendanceRecord> _records = [];
  bool _loading = false;
  final _api = ApiClient();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final auth = ref.read(authProvider);
    final studentId = auth.linkedStudentId;
    if (studentId == null) return;
    setState(() => _loading = true);
    try {
      final resp = await _api.get('/attendance/history', params: {'student_id': studentId});
      setState(() {
        _records = (resp.data as List).map((e) => AttendanceRecord.fromJson(e as Map<String, dynamic>)).toList();
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_records.isEmpty) return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.history_toggle_off, size: 60, color: cs.onSurface.withOpacity(0.3)),
      const SizedBox(height: 12),
      const Text('No attendance history found.'),
    ]));

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _records.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (_, i) {
        final r = _records[i];
        return ListTile(
          leading: CircleAvatar(
            backgroundColor: Colors.green.withOpacity(0.15),
            child: const Icon(Icons.check, color: Colors.green),
          ),
          title: Text(r.date, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text('Session ${r.session}  •  ${r.timestamp}'),
          trailing: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(color: Colors.green.withOpacity(0.15), borderRadius: BorderRadius.circular(6)),
            child: Text(r.status, style: const TextStyle(color: Colors.green, fontSize: 12, fontWeight: FontWeight.w600)),
          ),
        );
      },
    );
  }
}
