/// screens/teacher/attendance_log_screen.dart
/// ============================================
/// View and filter attendance records — maps from pages/3_Attendance_Log.py
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../core/api_client.dart';
import '../../models/attendance.dart';

class AttendanceLogScreen extends ConsumerStatefulWidget {
  const AttendanceLogScreen({super.key});

  @override
  ConsumerState<AttendanceLogScreen> createState() => _AttendanceLogScreenState();
}

class _AttendanceLogScreenState extends ConsumerState<AttendanceLogScreen> {
  DateTime _selectedDate = DateTime.now();
  String _selectedSession = 'Both';
  List<AttendanceRecord> _records = [];
  bool _loading = false;
  String? _error;

  final _api = ApiClient();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
      final params = <String, String>{'date_str': dateStr};
      if (_selectedSession != 'Both') params['session'] = _selectedSession;

      final resp = await _api.get('/attendance', params: params);
      final list = (resp.data as List<dynamic>)
          .map((e) => AttendanceRecord.fromJson(e as Map<String, dynamic>))
          .toList();
      setState(() { _records = list; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2024),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _selectedDate = picked);
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Filter bar ─────────────────────────────────────────────────────
          Row(
            children: [
              Expanded(
                child: InkWell(
                  onTap: _pickDate,
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF252540),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.calendar_today, size: 18, color: cs.primary),
                        const SizedBox(width: 8),
                        Text(
                          DateFormat('d MMM yyyy').format(_selectedDate),
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              DropdownButton<String>(
                value: _selectedSession,
                underline: const SizedBox(),
                dropdownColor: const Color(0xFF252540),
                borderRadius: BorderRadius.circular(12),
                items: ['Both', 'FN', 'AN']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (v) {
                  setState(() => _selectedSession = v!);
                  _load();
                },
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: _load,
                icon: Icon(Icons.refresh, color: cs.primary),
                tooltip: 'Refresh',
              ),
            ],
          ),
          const SizedBox(height: 12),

          // ── Summary chip ───────────────────────────────────────────────────
          if (!_loading && _error == null)
            Chip(
              avatar: Icon(Icons.check_circle, color: cs.primary, size: 18),
              label: Text('${_records.length} present'),
              padding: EdgeInsets.zero,
            ),
          const SizedBox(height: 12),

          // ── List ───────────────────────────────────────────────────────────
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Text(_error!, style: TextStyle(color: cs.error)))
                    : _records.isEmpty
                        ? Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.inbox, size: 60, color: cs.onSurface.withOpacity(0.3)),
                                const SizedBox(height: 12),
                                Text('No attendance records', style: TextStyle(color: cs.onSurface.withOpacity(0.5))),
                              ],
                            ),
                          )
                        : ListView.separated(
                            itemCount: _records.length,
                            separatorBuilder: (_, __) => const Divider(height: 1),
                            itemBuilder: (context, i) {
                              final rec = _records[i];
                              return ListTile(
                                leading: CircleAvatar(
                                  backgroundColor: cs.primary.withOpacity(0.15),
                                  child: Text(
                                    rec.name[0].toUpperCase(),
                                    style: TextStyle(color: cs.primary, fontWeight: FontWeight.bold),
                                  ),
                                ),
                                title: Text(rec.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                                subtitle: Text('${rec.rollNo}  •  ${rec.classSection}  •  ${rec.session}'),
                                trailing: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                      decoration: BoxDecoration(
                                        color: Colors.green.withOpacity(0.2),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        rec.status,
                                        style: const TextStyle(color: Colors.green, fontSize: 12, fontWeight: FontWeight.w600),
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(rec.timestamp, style: TextStyle(fontSize: 11, color: cs.onSurface.withOpacity(0.5))),
                                  ],
                                ),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}
