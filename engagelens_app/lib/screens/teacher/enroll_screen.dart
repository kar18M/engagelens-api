/// screens/teacher/enroll_screen.dart
/// =====================================
/// Multi-angle student enrollment — maps from pages/4_Enroll_Student.py
library;

import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';

class EnrollScreen extends StatefulWidget {
  const EnrollScreen({super.key});
  @override
  State<EnrollScreen> createState() => _EnrollScreenState();
}

class _EnrollScreenState extends State<EnrollScreen> {
  final _formKey = GlobalKey<FormState>();
  final _idCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  final _rollCtrl = TextEditingController();
  final _sectionCtrl = TextEditingController();

  final Map<String, Uint8List?> _angleImages = {
    'front': null,
    'left_profile': null,
    'right_profile': null,
    'tilt_up': null,
    'tilt_down': null,
  };

  bool _enrolling = false;
  String? _resultMsg;
  bool? _success;
  final _picker = ImagePicker();
  final _api = ApiClient();

  Future<void> _pickAngle(String angle) async {
    final xfile = await _picker.pickImage(source: ImageSource.camera, imageQuality: 90);
    if (xfile == null) return;
    final bytes = await xfile.readAsBytes();
    setState(() => _angleImages[angle] = bytes);
  }

  Future<void> _enroll() async {
    if (!_formKey.currentState!.validate()) return;
    final filled = _angleImages.values.where((v) => v != null).length;
    if (filled < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Capture at least 2 angle photos (front + one profile)')),
      );
      return;
    }

    setState(() { _enrolling = true; _resultMsg = null; });

    try {
      final fields = <String, dynamic>{
        'student_id': _idCtrl.text.trim(),
        'name': _nameCtrl.text.trim(),
        'roll_no': _rollCtrl.text.trim(),
        'class_section': _sectionCtrl.text.trim(),
      };

      for (final entry in _angleImages.entries) {
        if (entry.value != null) {
          fields[entry.key] = MultipartFile.fromBytes(entry.value!, filename: '${entry.key}.jpg');
        }
      }

      final formData = FormData.fromMap(fields);
      final resp = await _api.postFormData('/enroll', formData);
      final data = resp.data as Map<String, dynamic>;
      setState(() {
        _success = data['success'] as bool;
        _resultMsg = data['message'] as String;
      });
    } catch (e) {
      setState(() { _success = false; _resultMsg = e.toString(); });
    } finally {
      setState(() => _enrolling = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Student info
            TextFormField(
              controller: _idCtrl,
              decoration: const InputDecoration(labelText: 'Student ID *', prefixIcon: Icon(Icons.badge_outlined)),
              validator: (v) => v!.isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _nameCtrl,
              decoration: const InputDecoration(labelText: 'Full Name *', prefixIcon: Icon(Icons.person_outline)),
              validator: (v) => v!.isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _rollCtrl,
                    decoration: const InputDecoration(labelText: 'Roll No', prefixIcon: Icon(Icons.numbers)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _sectionCtrl,
                    decoration: const InputDecoration(labelText: 'Class/Section', prefixIcon: Icon(Icons.class_outlined)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Text('Face Photos (min 2 angles)', style: TextStyle(fontWeight: FontWeight.bold, color: cs.primary)),
            const SizedBox(height: 4),
            Text('front + left_profile or right_profile required', style: TextStyle(fontSize: 12, color: cs.onSurface.withOpacity(0.5))),
            const SizedBox(height: 12),

            // Angle grid
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
                childAspectRatio: 1,
              ),
              itemCount: _angleImages.length,
              itemBuilder: (_, i) {
                final angle = _angleImages.keys.elementAt(i);
                final img = _angleImages[angle];
                return GestureDetector(
                  onTap: () => _pickAngle(angle),
                  child: Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF252540),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: img != null ? cs.primary : cs.onSurface.withOpacity(0.2),
                        width: img != null ? 2 : 1,
                      ),
                    ),
                    child: img != null
                        ? ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: Image.memory(img, fit: BoxFit.cover),
                          )
                        : Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.add_a_photo, color: cs.onSurface.withOpacity(0.4)),
                              const SizedBox(height: 4),
                              Text(angle.replaceAll('_', '\n'), textAlign: TextAlign.center,
                                  style: TextStyle(fontSize: 10, color: cs.onSurface.withOpacity(0.5))),
                            ],
                          ),
                  ),
                );
              },
            ),

            const SizedBox(height: 20),

            // Result feedback
            if (_resultMsg != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: (_success == true ? Colors.green : cs.error).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: (_success == true ? Colors.green : cs.error).withOpacity(0.4)),
                ),
                child: Row(
                  children: [
                    Icon(_success == true ? Icons.check_circle : Icons.error,
                        color: _success == true ? Colors.green : cs.error),
                    const SizedBox(width: 8),
                    Expanded(child: Text(_resultMsg!)),
                  ],
                ),
              ),

            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton.icon(
                onPressed: _enrolling ? null : _enroll,
                icon: _enrolling
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.person_add),
                label: Text(_enrolling ? 'Enrolling…' : 'Enroll Student'),
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }
}
