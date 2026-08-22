/// core/api_client.dart
/// ====================
/// Dio HTTP client configured for the EngageLens FastAPI server.
/// Automatically attaches the JWT Bearer token to every request.
library;

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Change this to switch between local dev and cloud deployment.
/// Cloud (Render):  'https://engagelens-api.onrender.com'
/// Local dev:       'http://10.242.159.207:8000'
const String kBaseUrl = 'https://engagelens-api.onrender.com';

const _storage = FlutterSecureStorage();

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;

  late final Dio _dio;

  ApiClient._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: kBaseUrl,
        // Render free plan sleeps after 15min idle — first request takes ~30s to wake
        connectTimeout: const Duration(seconds: 40),
        receiveTimeout: const Duration(seconds: 90), // Face recognition is slow on free CPU
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
