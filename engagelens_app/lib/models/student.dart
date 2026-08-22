/// models/student.dart
class StudentModel {
  final String studentId;
  final String name;
  final String rollNo;
  final String classSection;
  final String? parentTelegramChatId;
  final String? enrolledOn;
  final List<String> anglesEnrolled;

  StudentModel({
    required this.studentId,
    required this.name,
    this.rollNo = '',
    this.classSection = '',
    this.parentTelegramChatId,
    this.enrolledOn,
    this.anglesEnrolled = const [],
  });

  factory StudentModel.fromJson(Map<String, dynamic> json) {
    return StudentModel(
      studentId: json['student_id'] as String,
      name: json['name'] as String,
      rollNo: (json['roll_no'] as String?) ?? '',
      classSection: (json['class_section'] as String?) ?? '',
      parentTelegramChatId: json['parent_telegram_chat_id'] as String?,
      enrolledOn: json['enrolled_on'] as String?,
      anglesEnrolled: (json['angles_enrolled'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }

  Map<String, dynamic> toJson() => {
        'student_id': studentId,
        'name': name,
        'roll_no': rollNo,
        'class_section': classSection,
        'parent_telegram_chat_id': parentTelegramChatId,
      };
}
