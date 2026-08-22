/// models/attendance.dart
class AttendanceRecord {
  final String studentId;
  final String name;
  final String rollNo;
  final String classSection;
  final String date;
  final String session;
  final String timestamp;
  final String status;
  final String matchedAngle;
  final double matchDistance;

  AttendanceRecord({
    required this.studentId,
    required this.name,
    this.rollNo = '',
    this.classSection = '',
    required this.date,
    required this.session,
    this.timestamp = '',
    this.status = 'Present',
    this.matchedAngle = '',
    this.matchDistance = 0.0,
  });

  factory AttendanceRecord.fromJson(Map<String, dynamic> json) {
    return AttendanceRecord(
      studentId: json['student_id'] as String,
      name: json['name'] as String,
      rollNo: (json['roll_no'] as String?) ?? '',
      classSection: (json['class_section'] as String?) ?? '',
      date: json['date'] as String,
      session: json['session'] as String,
      timestamp: (json['timestamp'] as String?) ?? '',
      status: (json['status'] as String?) ?? 'Present',
      matchedAngle: (json['matched_angle'] as String?) ?? '',
      matchDistance: ((json['match_distance'] as num?) ?? 0).toDouble(),
    );
  }
}
