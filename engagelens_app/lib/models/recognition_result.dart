/// models/recognition_result.dart
class RecognitionResult {
  final String studentId;
  final String name;
  final String matchedAngle;
  final double distance;
  final double detScore;
  final List<int> bbox; // [x1, y1, x2, y2]

  bool get isKnown => studentId != 'Unknown';

  RecognitionResult({
    required this.studentId,
    required this.name,
    required this.matchedAngle,
    required this.distance,
    required this.detScore,
    required this.bbox,
  });

  factory RecognitionResult.fromJson(Map<String, dynamic> json) {
    return RecognitionResult(
      studentId: json['student_id'] as String,
      name: json['name'] as String,
      matchedAngle: json['matched_angle'] as String,
      distance: ((json['distance'] as num?) ?? 0).toDouble(),
      detScore: ((json['det_score'] as num?) ?? 0).toDouble(),
      bbox: (json['bbox'] as List<dynamic>).map((e) => (e as num).toInt()).toList(),
    );
  }
}

class RecognizeResponse {
  final List<RecognitionResult> results;
  final int totalDetected;
  final int totalRecognised;

  RecognizeResponse({
    required this.results,
    required this.totalDetected,
    required this.totalRecognised,
  });

  factory RecognizeResponse.fromJson(Map<String, dynamic> json) {
    final list = (json['results'] as List<dynamic>)
        .map((e) => RecognitionResult.fromJson(e as Map<String, dynamic>))
        .toList();
    return RecognizeResponse(
      results: list,
      totalDetected: (json['total_detected'] as num).toInt(),
      totalRecognised: (json['total_recognised'] as num).toInt(),
    );
  }
}
