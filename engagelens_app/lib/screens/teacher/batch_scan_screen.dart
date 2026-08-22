/// screens/teacher/batch_scan_screen.dart
library;

import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';
import '../../models/recognition_result.dart';

class BatchScanScreen extends StatefulWidget {
  const BatchScanScreen({super.key});
  @override
  State<BatchScanScreen> createState() => _BatchScanScreenState();
}

class _BatchScanScreenState extends State<BatchScanScreen> {
  Uint8List? _imageBytes;
  bool _processing = false;
  RecognizeResponse? _result;
  String _session = 'FN';
  final _api = ApiClient();
  final _picker = ImagePicker();

  Future<void> _pickImage(ImageSource source) async {
    final xfile = await _picker.pickImage(source: source, imageQuality: 85);
    if (xfile == null) return;
    final bytes = await xfile.readAsBytes();
    setState(() { _imageBytes = bytes; _result = null; });
  }

  Future<void> _processImage() async {
    if (_imageBytes == null) return;
    setState(() => _processing = true);
    try {
      final formData = FormData.fromMap({
        'image': MultipartFile.fromBytes(_imageBytes!, filename: 'batch.jpg'),
      });
      final resp = await _api.postFormData('/recognize', formData);
      final rr = RecognizeResponse.fromJson(resp.data as Map<String, dynamic>);
      // Mark attendance for all recognised
      for (final r in rr.results.where((r) => r.isKnown)) {
        try {
          await _api.post('/attendance/mark', data: {
            'student_id': r.studentId,
            'name': r.name,
            'matched_angle': r.matchedAngle,
            'match_distance': r.distance,
            'session': _session,
          });
        } catch (_) {}
      }
      setState(() => _result = rr);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      setState(() => _processing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Session selector
          Row(
            children: [
              const Text('Session:'),
              const SizedBox(width: 12),
              DropdownButton<String>(
                value: _session,
                underline: const SizedBox(),
                dropdownColor: const Color(0xFF252540),
                items: ['FN', 'AN'].map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
                onChanged: (v) => setState(() => _session = v!),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Pick buttons
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: () => _pickImage(ImageSource.camera),
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Take Photo'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _pickImage(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Gallery'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Preview
          if (_imageBytes != null)
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.memory(_imageBytes!, height: 220, width: double.infinity, fit: BoxFit.cover),
            ),
          const SizedBox(height: 12),
          if (_imageBytes != null)
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton.icon(
                onPressed: _processing ? null : _processImage,
                icon: _processing
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.scanner),
                label: Text(_processing ? 'Processing…' : 'Recognise & Mark Attendance'),
              ),
            ),
          const SizedBox(height: 16),
          // Results
          if (_result != null) ...[
            Row(
              children: [
                _chip(Icons.face, '${_result!.totalDetected} detected', cs.primary),
                const SizedBox(width: 8),
                _chip(Icons.check, '${_result!.totalRecognised} recognised', Colors.green),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: ListView.builder(
                itemCount: _result!.results.length,
                itemBuilder: (_, i) {
                  final r = _result!.results[i];
                  return ListTile(
                    leading: CircleAvatar(
                      backgroundColor: (r.isKnown ? Colors.green : cs.error).withOpacity(0.2),
                      child: Icon(r.isKnown ? Icons.check : Icons.person_off,
                          color: r.isKnown ? Colors.green : cs.error),
                    ),
                    title: Text(r.name),
                    subtitle: Text(r.isKnown ? '${r.matchedAngle} | dist ${r.distance.toStringAsFixed(3)}' : 'Unknown'),
                  );
                },
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _chip(IconData icon, String label, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
    child: Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, color: color, size: 16),
      const SizedBox(width: 4),
      Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13)),
    ]),
  );
}
