/// screens/student/dashboard_screen.dart
/// ========================================
/// Student's own attendance statistics and pie chart.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../core/api_client.dart';
import '../../core/auth_provider.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});
  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  Map<String, dynamic>? _stats;
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
      final resp = await _api.get('/attendance/stats', params: {'student_id': studentId});
      setState(() { _stats = resp.data as Map<String, dynamic>; });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final auth = ref.watch(authProvider);

    if (_loading) return const Center(child: CircularProgressIndicator());

    if (_stats == null) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.person_off, size: 60, color: cs.onSurface.withOpacity(0.3)),
        const SizedBox(height: 12),
        const Text('No linked student record found.'),
      ]));
    }

    final present = (_stats!['present_days'] as num).toInt();
    final absent  = (_stats!['absent_days']  as num).toInt();
    final total   = present + absent;
    final pct     = total == 0 ? 0.0 : (present / total * 100);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Welcome
          Text('Welcome back,', style: TextStyle(color: cs.onSurface.withOpacity(0.55), fontSize: 14)),
          Text(auth.fullName ?? '', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 24),

          // Pie chart card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Text('Attendance Overview', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: cs.primary)),
                  const SizedBox(height: 20),
                  SizedBox(
                    height: 180,
                    child: PieChart(
                      PieChartData(
                        sections: [
                          PieChartSectionData(
                            value: present.toDouble(),
                            color: cs.primary,
                            title: 'Present\n$present',
                            radius: 70,
                            titleStyle: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                          ),
                          PieChartSectionData(
                            value: absent.toDouble(),
                            color: cs.error,
                            title: 'Absent\n$absent',
                            radius: 70,
                            titleStyle: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                          ),
                        ],
                        sectionsSpace: 3,
                        centerSpaceRadius: 40,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    '${pct.toStringAsFixed(1)}% Attendance',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: pct >= 75 ? Colors.green : cs.error),
                  ),
                  Text(
                    '$present / $total days',
                    style: TextStyle(color: cs.onSurface.withOpacity(0.55)),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Stat chips
          Row(
            children: [
              _statCard(Icons.check_circle, 'Present', '$present', Colors.green, cs),
              const SizedBox(width: 12),
              _statCard(Icons.cancel, 'Absent', '$absent', cs.error, cs),
              const SizedBox(width: 12),
              _statCard(Icons.calendar_month, 'Total', '$total', cs.primary, cs),
            ],
          ),
        ],
      ),
    );
  }

  Widget _statCard(IconData icon, String label, String value, Color color, ColorScheme cs) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 6),
            Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
            Text(label, style: TextStyle(fontSize: 11, color: cs.onSurface.withOpacity(0.55))),
          ],
        ),
      ),
    );
  }
}
