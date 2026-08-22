/// core/api_client.dart
/// ====================
/// Dio HTTP client configured for the EngageLens FastAPI server.
/// Automatically attaches the JWT Bearer token to every request.
library;

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Change this to your server's LAN IP before building the APK.
/// Example: 'http://192.168.1.42:8000'
const String kBaseUrl = 'http://10.242.159.207:8000';

const _storage = FlutterSecureStorage();

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;

  late final Dio _dio;

  ApiClient._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: kBaseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Content-Type': 'application/json'},
      ),
    );

    // JWT interceptor — attach token to every request
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'jwt_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (err, handler) {
          handler.next(err);
        },
      ),
    );
  }

  Dio get dio => _dio;

  // ── Convenience wrappers ─────────────────────────────────────────────────────

  Future<Response<T>> get<T>(String path, {Map<String, dynamic>? params}) =>
      _dio.get<T>(path, queryParameters: params);

  Future<Response<T>> post<T>(String path, {dynamic data}) =>
      _dio.post<T>(path, data: data);

  Future<Response<T>> put<T>(String path, {dynamic data}) =>
      _dio.put<T>(path, data: data);

  Future<Response<T>> delete<T>(String path) => _dio.delete<T>(path);

  Future<Response<T>> postFormData<T>(String path, FormData formData) =>
      _dio.post<T>(path, data: formData);

  // ── Token management ─────────────────────────────────────────────────────────

  static Future<void> saveToken(String token) async {
    await _storage.write(key: 'jwt_token', value: token);
  }

  static Future<void> deleteToken() async {
    await _storage.delete(key: 'jwt_token');
  }

  static Future<String?> getToken() async {
    return _storage.read(key: 'jwt_token');
  }
}
