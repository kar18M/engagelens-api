/// screens/teacher/live_scan_screen.dart
/// =======================================
/// Live camera feed → server recognition → face overlay boxes.
/// Maps from pages/1_Live_Attendance.py
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';
import '../../models/recognition_result.dart';
import '../../widgets/face_overlay_painter.dart';

class LiveScanScreen extends StatefulWidget {
  const LiveScanScreen({super.key});

  @override
  State<LiveScanScreen> createState() => _LiveScanScreenState();
}

class _LiveScanScreenState extends State<LiveScanScreen> {
  CameraController? _camCtrl;
  List<CameraDescription> _cameras = [];
  bool _camReady = false;
  bool _scanning = false;

  List<RecognitionResult> _results = [];
  Size _previewSize = Size.zero;

  int _recognised = 0;
  int _marked = 0;
  String _session = 'FN';

  Timer? _scanTimer;
  final _api = ApiClient();

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    _cameras = await availableCameras();
    if (_cameras.isEmpty) {
      if (mounted) setState(() => _camReady = false);
      return;
    }
    // Prefer back camera (smartboard camera)
    final cam = _cameras.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.back,
      orElse: () => _cameras.first,
    );
    _camCtrl = CameraController(cam, ResolutionPreset.high, enableAudio: false);
    await _camCtrl!.initialize();
    if (mounted) {
      _previewSize = _camCtrl!.value.previewSize ?? Size.zero;
      setState(() => _camReady = true);
    }
  }

  void _startScan() {
    setState(() => _scanning = true);
    _scanTimer = Timer.periodic(const Duration(seconds: 2), (_) => _captureAndRecognize());
  }

  void _stopScan() {
    _scanTimer?.cancel();
    setState(() { _scanning = false; _results = []; });
  }

  Future<void> _captureAndRecognize() async {
    if (_camCtrl == null || !_camCtrl!.value.isInitialized) return;
    try {
      final xfile = await _camCtrl!.takePicture();
      final bytes = await xfile.readAsBytes();

      final formData = FormData.fromMap({
        'image': MultipartFile.fromBytes(bytes, filename: 'frame.jpg'),
      });

      final resp = await _api.postFormData('/recognize', formData);
      final rr = RecognizeResponse.fromJson(resp.data as Map<String, dynamic>);

      if (mounted) {
        setState(() {
          _results = rr.results;
          _recognised = rr.totalRecognised;
        });
      }

      // Auto-mark attendance for recognised students
      for (final r in rr.results.where((r) => r.isKnown)) {
        try {
          await _api.post('/attendance/mark', data: {
            'student_id': r.studentId,
            'name': r.name,
            'matched_angle': r.matchedAngle,
            'match_distance': r.distance,
            'session': _session,
          });
          if (mounted) setState(() => _marked++);
        } catch (_) {}
      }
    } catch (_) {
      // Silent — failed frames are skipped
    }
  }

  @override
  void dispose() {
    _scanTimer?.cancel();
    _camCtrl?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      body: Column(
        children: [
          // ── Status bar ───────────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.all(12),
            color: const Color(0xFF1A1A2E),
            child: Row(
              children: [
                _statChip(Icons.face, '$_recognised detected', cs.primary),
                const SizedBox(width: 8),
                _statChip(Icons.check, '$_marked marked', Colors.green),
                const Spacer(),
                DropdownButton<String>(
                  value: _session,
                  underline: const SizedBox(),
                  dropdownColor: const Color(0xFF252540),
                  items: ['FN', 'AN'].map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
                  onChanged: (v) => setState(() => _session = v!),
                ),
              ],
            ),
          ),

          // ── Camera preview + overlay ────────────────────────────────────
          Expanded(
            child: _camReady && _camCtrl != null
                ? LayoutBuilder(
                    builder: (ctx, constraints) {
                      return Stack(
                        fit: StackFit.expand,
                        children: [
                          CameraPreview(_camCtrl!),
                          CustomPaint(
                            painter: FaceOverlayPainter(
                              results: _results,
                              imageSize: _previewSize,
                              canvasSize: constraints.biggest,
                            ),
                          ),
                        ],
                      );
                    },
                  )
                : Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.videocam_off, size: 60, color: cs.onSurface.withOpacity(0.3)),
                        const SizedBox(height: 12),
                        const Text('Camera not available'),
                      ],
                    ),
                  ),
          ),

          // ── Start / Stop button ─────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.all(20),
            child: SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton.icon(
                onPressed: _camReady
                    ? (_scanning ? _stopScan : _startScan)
                    : null,
                icon: Icon(_scanning ? Icons.stop : Icons.play_arrow),
                label: Text(_scanning ? 'Stop Scan' : 'Start Live Scan'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _scanning ? cs.error : cs.primary,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _statChip(IconData icon, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 16),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13)),
        ],
      ),
    );
  }
}
