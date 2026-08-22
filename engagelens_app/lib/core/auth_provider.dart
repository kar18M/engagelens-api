/// core/auth_provider.dart
/// =======================
/// Riverpod state management for authentication.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../core/api_client.dart';

const _storage = FlutterSecureStorage();

class AuthState {
  final bool isAuthenticated;
  final String? token;
  final String? role;
  final String? userId;
  final String? fullName;
  final String? username;
  final String? linkedStudentId;
  final List<String> assignedSections;

  const AuthState({
    this.isAuthenticated = false,
    this.token,
    this.role,
    this.userId,
    this.fullName,
    this.username,
    this.linkedStudentId,
    this.assignedSections = const [],
  });

  AuthState copyWith({
    bool? isAuthenticated,
    String? token,
    String? role,
    String? userId,
    String? fullName,
    String? username,
    String? linkedStudentId,
    List<String>? assignedSections,
  }) {
    return AuthState(
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      token: token ?? this.token,
      role: role ?? this.role,
      userId: userId ?? this.userId,
      fullName: fullName ?? this.fullName,
      username: username ?? this.username,
      linkedStudentId: linkedStudentId ?? this.linkedStudentId,
      assignedSections: assignedSections ?? this.assignedSections,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState());

  final ApiClient _api = ApiClient();

  /// Try to restore session from secure storage on app start.
  Future<void> restore() async {
    final token = await _storage.read(key: 'jwt_token');
    final role = await _storage.read(key: 'user_role');
    final userId = await _storage.read(key: 'user_id');
    final fullName = await _storage.read(key: 'full_name');
    final username = await _storage.read(key: 'username');
    final linkedStudentId = await _storage.read(key: 'linked_student_id');

    if (token != null && role != null) {
      state = AuthState(
        isAuthenticated: true,
        token: token,
        role: role,
        userId: userId,
        fullName: fullName,
        username: username,
        linkedStudentId: linkedStudentId,
      );
    }
  }

  /// Login with username+password. Returns null on success, error string on failure.
  Future<String?> login(String username, String password) async {
    try {
      final resp = await _api.post('/auth/login', data: {
        'username': username,
        'password': password,
      });
      final data = resp.data as Map<String, dynamic>;
      final token = data['access_token'] as String;
      final role = data['role'] as String;
      final userId = data['user_id'] as String;
      final fullName = data['full_name'] as String;

      await ApiClient.saveToken(token);
      await _storage.write(key: 'user_role', value: role);
      await _storage.write(key: 'user_id', value: userId);
      await _storage.write(key: 'full_name', value: fullName);
      await _storage.write(key: 'username', value: username);

      // Fetch full profile for linked_student_id
      try {
        final meResp = await _api.get('/auth/me');
        final meData = meResp.data as Map<String, dynamic>;
        final linkedId = meData['linked_student_id'] as String?;
        if (linkedId != null) {
          await _storage.write(key: 'linked_student_id', value: linkedId);
        }
        state = AuthState(
          isAuthenticated: true,
          token: token,
          role: role,
          userId: userId,
          fullName: fullName,
          username: username,
          linkedStudentId: linkedId,
        );
      } catch (_) {
        state = AuthState(
          isAuthenticated: true,
          token: token,
          role: role,
          userId: userId,
          fullName: fullName,
          username: username,
        );
      }
      return null;
    } on Exception catch (e) {
      return e.toString().replaceAll('Exception: ', '');
    }
  }

  Future<void> logout() async {
    await ApiClient.deleteToken();
    await _storage.deleteAll();
    state = const AuthState();
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});
