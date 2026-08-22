/// screens/admin/class_management_screen.dart
library;

import 'package:flutter/material.dart';
import '../../core/api_client.dart';

class ClassManagementScreen extends StatefulWidget {
  const ClassManagementScreen({super.key});
  @override
  State<ClassManagementScreen> createState() => _ClassManagementScreenState();
}

class _ClassManagementScreenState extends State<ClassManagementScreen> {
  List<dynamic> _classes = [];
  bool _loading = false;
  final _api = ApiClient();
  final _nameCtrl = TextEditingController();

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final resp = await _api.get('/classes/');
      setState(() => _classes = resp.data as List);
    } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
    finally { setState(() => _loading = false); }
  }

  Future<void> _create() async {
    if (_nameCtrl.text.trim().isEmpty) return;
    try {
      await _api.post('/classes/', data: {'name': _nameCtrl.text.trim()});
      _nameCtrl.clear();
      _load();
    } catch (e) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'New class name'))),
              const SizedBox(width: 12),
              ElevatedButton(onPressed: _create, child: const Text('Add')),
            ],
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    itemCount: _classes.length,
                    itemBuilder: (_, i) {
                      final c = _classes[i] is Map ? _classes[i] as Map : {'name': _classes[i]};
                      return ListTile(
                        leading: const Icon(Icons.class_),
                        title: Text(c['name'] as String? ?? '$c'),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
