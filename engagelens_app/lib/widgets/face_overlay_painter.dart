/// widgets/face_overlay_painter.dart
/// ====================================
/// CustomPainter that draws green/red bounding boxes on top of CameraPreview.
library;

import 'package:flutter/material.dart';
import '../models/recognition_result.dart';

class FaceOverlayPainter extends CustomPainter {
  final List<RecognitionResult> results;
  final Size imageSize;
  final Size canvasSize;

  FaceOverlayPainter({
    required this.results,
    required this.imageSize,
    required this.canvasSize,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (imageSize.width == 0 || imageSize.height == 0) return;

    final scaleX = canvasSize.width / imageSize.width;
    final scaleY = canvasSize.height / imageSize.height;

    for (final result in results) {
      if (result.bbox.length < 4) continue;

      final x1 = result.bbox[0] * scaleX;
      final y1 = result.bbox[1] * scaleY;
      final x2 = result.bbox[2] * scaleX;
      final y2 = result.bbox[3] * scaleY;

      final rect = Rect.fromLTRB(x1, y1, x2, y2);
      final isKnown = result.isKnown;

      final boxColor = isKnown ? const Color(0xFF1EDB50) : const Color(0xFFFF4444);
      final boxPaint = Paint()
        ..color = boxColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5;

      // Draw rounded bounding box
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(4)),
        boxPaint,
      );

      // Draw label background
      final label = isKnown ? result.name : 'Unknown';
      final subLabel = isKnown ? '${result.matchedAngle} | ${result.distance.toStringAsFixed(3)}' : 'conf ${result.detScore.toStringAsFixed(2)}';

      final bgPaint = Paint()..color = boxColor.withOpacity(0.85);
      final labelHeight = 36.0;
      final labelY = y1 > labelHeight + 4 ? y1 - labelHeight - 4 : y2 + 4;

      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x1, labelY, x2 - x1, labelHeight),
          const Radius.circular(4),
        ),
        bgPaint,
      );

      // Draw name text
      _drawText(canvas, label, x1 + 4, labelY + 2, 13, bold: true);
      _drawText(canvas, subLabel, x1 + 4, labelY + 18, 10);
    }
  }

  void _drawText(Canvas canvas, String text, double x, double y, double fontSize, {bool bold = false}) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: Colors.white,
          fontSize: fontSize,
          fontWeight: bold ? FontWeight.bold : FontWeight.normal,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    tp.layout();
    tp.paint(canvas, Offset(x, y));
  }

  @override
  bool shouldRepaint(FaceOverlayPainter old) =>
      old.results != results || old.imageSize != imageSize;
}
