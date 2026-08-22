/// screens/teacher/alerts_screen.dart
/// =====================================
/// View absentees and send Telegram alerts — maps from portals/teacher_portal/alerts.py
library;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/api_client.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});
  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  DateTime _date = DateTime.now();
  String _session = 'FN';
  List<Map<String, dynamic>> _absentees = [];
  bool _loading = false;
  bool _sending = false;
  Map<String, dynamic>? _sendResult;
  final _api = ApiClient();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _sendResult = null; });
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(_date);
      final resp = await _api.get('/attendance/absentees', params: {'date_str': dateStr, 'session': _session});
      setState(() { _absentees = (resp.data as List).cast<Map<String, dynamic>>(); });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _sendAlerts() async {
    setState(() { _sending = true; _sendResult = null; });
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(_date);
      final resp = await _api.post('/alerts/send', data: {'date_str': dateStr, 'session': _session});
      setState(() => _sendResult = resp.data as Map<String, dynamic>);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      setState(() => _sending = false);
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
          // Filter
          Row(
            children: [
              Expanded(
                child: InkWell(
                  onTap: () async {
                    final p = await showDatePicker(context: context, initialDate: _date, firstDate: DateTime(2024), lastDate: DateTime.now());
                    if (p != null) { setState(() => _date = p); _load(); }
                  },
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(color: const Color(0xFF252540), borderRadius: BorderRadius.circular(12)),
                    child: Row(children: [
                      Icon(Icons.calendar_today, size: 18, color: cs.primary),
                      const SizedBox(width: 8),
                      Text(DateFormat('d MMM yyyy').format(_date), style: const TextStyle(fontWeight: FontWeight.w600)),
                    ]),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              DropdownButton<String>(
                value: _session, underline: const SizedBox(), dropdownColor: const Color(0xFF252540),
                items: ['FN', 'AN'].map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
                onChanged: (v) { setState(() => _session = v!); _load(); },
              ),
              const SizedBox(width: 8),
              IconButton(onPressed: _load, icon: Icon(Icons.refresh, color: cs.primary)),
            ],
          ),
          const SizedBox(height: 12),
          // Absentee count + send button
          Row(
            children: [
              Chip(avatar: Icon(Icons.person_off, color: cs.error, size: 18), label: Text('${_absentees.length} absent')),
              const Spacer(),
              ElevatedButton.icon(
                onPressed: _sending || _absentees.isEmpty ? null : _sendAlerts,
                icon: _sending
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.send, size: 18),
                label: Text(_sending ? 'Sending…' : 'Send Alerts'),
                style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
              ),
            ],
          ),
          // Send result
          if (_sendResult != null)
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.green.withOpacity(0.3)),
              ),
              child: Text(_sendResult!['message'] as String, style: const TextStyle(color: Colors.green)),
            ),
          const SizedBox(height: 12),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _absentees.isEmpty
                    ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                        Icon(Icons.celebration, size: 60, color: Colors.green.withOpacity(0.4)),
                        const SizedBox(height: 12),
                        const Text('No absentees — full attendance!'),
                      ]))
                    : ListView.builder(
                        itemCount: _absentees.length,
                        itemBuilder: (_, i) {
                          final a = _absentees[i];
                          final hasChatId = (a['parent_telegram_chat_id'] as String?) != null;
                          return ListTile(
                            leading: CircleAvatar(
                              backgroundColor: cs.error.withOpacity(0.15),
                              child: Text((a['name'] as String)[0], style: TextStyle(color: cs.error)),
                            ),
                            title: Text(a['name'] as String),
                            subtitle: Text('${a['roll_no']}  •  ${a['class_section']}'),
                            trailing: Icon(
                              hasChatId ? Icons.telegram : Icons.link_off,
                              color: hasChatId ? const Color(0xFF0088CC) : cs.onSurface.withOpacity(0.3),
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
