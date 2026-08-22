/// screens/teacher/override_screen.dart
library;

import 'package:flutter/material.dart';

import '../../core/api_client.dart';

class OverrideScreen extends StatefulWidget {
  const OverrideScreen({super.key});
  @override
  State<OverrideScreen> createState() => _OverrideScreenState();
}

class _OverrideScreenState extends State<OverrideScreen> {
  final _studentIdCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  String _session = 'FN';
  bool _marking = false;
  String? _msg;
  bool? _ok;
  final _api = ApiClient();

  Future<void> _mark() async {
    final id = _studentIdCtrl.text.trim();
    final name = _nameCtrl.text.trim();
    if (id.isEmpty || name.isEmpty) return;
    setState(() { _marking = true; _msg = null; });
    try {
      final resp = await _api.post('/attendance/mark', data: {
        'student_id': id,
        'name': name,
        'matched_angle': 'manual',
        'match_distance': 0.0,
        'session': _session,
      });
      final data = resp.data as Map<String, dynamic>;
      setState(() { _ok = data['inserted'] as bool; _msg = data['message'] as String; });
    } catch (e) {
      setState(() { _ok = false; _msg = e.toString(); });
    } finally {
      setState(() => _marking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Manual Override')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            TextFormField(controller: _studentIdCtrl, decoration: const InputDecoration(labelText: 'Student ID', prefixIcon: Icon(Icons.badge_outlined))),
            const SizedBox(height: 12),
            TextFormField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Student Name', prefixIcon: Icon(Icons.person_outline))),
            const SizedBox(height: 12),
            Row(children: [
              const Text('Session:'),
              const SizedBox(width: 12),
              DropdownButton<String>(
                value: _session, underline: const SizedBox(), dropdownColor: const Color(0xFF252540),
                items: ['FN', 'AN'].map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
                onChanged: (v) => setState(() => _session = v!),
              ),
            ]),
            const SizedBox(height: 20),
            if (_msg != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: (_ok == true ? Colors.green : cs.error).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: (_ok == true ? Colors.green : cs.error).withOpacity(0.4)),
                ),
                child: Row(children: [
                  Icon(_ok == true ? Icons.check : Icons.error, color: _ok == true ? Colors.green : cs.error),
                  const SizedBox(width: 8),
                  Expanded(child: Text(_msg!)),
                ]),
              ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity, height: 52,
              child: ElevatedButton.icon(
                onPressed: _marking ? null : _mark,
                icon: const Icon(Icons.edit_calendar),
                label: Text(_marking ? 'Marking…' : 'Mark Present Manually'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
