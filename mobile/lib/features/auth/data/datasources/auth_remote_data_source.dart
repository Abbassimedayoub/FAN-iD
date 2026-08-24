import 'package:dio/dio.dart';

import '../../../../core/errors/failure.dart';
import '../../../../core/network/dio_client.dart';
import '../../domain/entities/login_session.dart';

class AuthRemoteDataSource {
  const AuthRemoteDataSource(this.dio);

  final Dio dio;

  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) async {
    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/v1/auth/login',
        data: {
          'email': email,
          'password': password,
          'client': 'mobile',
          'fingerprint': fingerprint,
          'platform': platform,
          'label': label,
        },
        options: Options(
          extra: const {
            DioClient.skipAuthRefreshKey: true,
          },
        ),
      );

      final body = response.data;
      if (body == null) {
        throw const ServerFailure();
      }

      return _parseLoginSession(body);
    } on DioException catch (error) {
      throw _mapLoginDioException(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Failure _mapLoginDioException(DioException exception) {
    final response = exception.response;
    final body = response?.data;

    if (response?.statusCode == 401 &&
        body is Map &&
        body['error'] is Map &&
        (body['error'] as Map)['code'] == 'INVALID_CREDENTIALS') {
      final error = body['error'] as Map;

      return BusinessFailure(
        'INVALID_CREDENTIALS',
        (error['message'] as String?) ?? 'Adresse ou mot de passe incorrect.',
        details:
            (error['details'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
    }

    return mapDioExceptionToFailure(exception);
  }

  Future<LoginSession> refresh({
    required String refreshToken,
    String? fingerprint,
  }) async {
    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/v1/auth/token/refresh',
        data: {
          'client': 'mobile',
          'refresh': refreshToken,
          'fingerprint': fingerprint,
        },
        options: Options(
          extra: const {
            DioClient.skipAuthRefreshKey: true,
          },
        ),
      );

      final body = response.data;
      if (body == null) {
        throw const ServerFailure();
      }

      return _parseLoginSession(body);
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  LoginSession _parseLoginSession(Map<String, dynamic> body) {
    final user = Map<String, dynamic>.from(body['user'] as Map);
    final rawDevice = body['device'];

    return LoginSession(
      access: body['access'] as String,
      refresh: body['refresh'] as String,
      user: AuthUser(
        id: user['id'] as String,
        email: user['email'] as String,
        firstName: user['first_name'] as String,
        lastName: user['last_name'] as String,
        role: user['role'] as String,
        createdAt: DateTime.parse(user['created_at'] as String),
      ),
      device: rawDevice == null
          ? null
          : _parseDevice(Map<String, dynamic>.from(rawDevice as Map)),
    );
  }

  AuthDevice _parseDevice(Map<String, dynamic> device) {
    return AuthDevice(
      id: device['id'] as String,
      label: device['label'] as String,
      boundAt: DateTime.parse(device['bound_at'] as String),
    );
  }
}
