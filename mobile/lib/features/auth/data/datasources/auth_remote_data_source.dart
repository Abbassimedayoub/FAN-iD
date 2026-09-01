import 'package:dio/dio.dart';

import '../../../../core/errors/failure.dart';
import '../../../../core/network/dio_client.dart';
import '../../domain/entities/device_reset_challenge.dart';
import '../../domain/entities/login_session.dart';
import '../../domain/entities/scanner_leave_challenge.dart';

class AuthRemoteDataSource {
  const AuthRemoteDataSource(this.dio);

  final Dio dio;

  Future<AuthUser> register({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    required bool termsAccepted,
    String? phone,
  }) async {
    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/v1/auth/register',
        data: {
          'email': email,
          'password': password,
          'first_name': firstName,
          'last_name': lastName,
          'date_of_birth': _formatDate(dateOfBirth),
          'terms_accepted': termsAccepted,
          if (phone != null) 'phone': phone,
        },
        options: Options(extra: const {DioClient.skipAuthRefreshKey: true}),
      );

      final body = response.data;
      if (body == null) {
        throw const ServerFailure();
      }

      return AuthUser(
        id: body['id'] as String,
        email: body['email'] as String,
        firstName: body['first_name'] as String,
        lastName: body['last_name'] as String,
        role: body['role'] as String,
        createdAt: DateTime.parse(body['created_at'] as String),
        mustChangePassword: (body['must_change_password'] as bool?) ?? false,
        phone: body['phone'] as String?,
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

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
        options: Options(extra: const {DioClient.skipAuthRefreshKey: true}),
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
        options: Options(extra: const {DioClient.skipAuthRefreshKey: true}),
      );

      final body = response.data;
      if (body == null) {
        throw const ServerFailure();
      }

      return _parseLoginSession(body);
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<ScannerLeaveChallenge> requestScannerLeaveCode() async {
    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/v1/organizers/scanner-leave/security-code',
        data: <String, dynamic>{},
      );

      final body = response.data;
      final challengeId = body?['challenge_id'];
      final expiresInSeconds = body?['expires_in_seconds'];

      if (challengeId is! String ||
          challengeId.trim().isEmpty ||
          expiresInSeconds is! int) {
        throw const ServerFailure();
      }

      return ScannerLeaveChallenge(
        challengeId: challengeId,
        expiresInSeconds: expiresInSeconds,
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<void> confirmScannerLeave({
    required String challengeId,
    required String code,
  }) async {
    try {
      await dio.post<void>(
        '/api/v1/organizers/scanner-leave/request',
        data: <String, dynamic>{
          'challenge_id': challengeId,
          'code': code.trim(),
        },
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<AuthUser> updatePhone({
    required String phone,
  }) async {
    try {
      final current = await dio.get<Map<String, dynamic>>(
        '/api/v1/auth/me',
      );

      final etag = current.headers.value(
        'etag',
      );

      if (etag == null || etag.trim().isEmpty) {
        throw const ServerFailure();
      }

      final response = await dio.patch<Map<String, dynamic>>(
        '/api/v1/auth/me',
        data: {
          'phone': phone.trim(),
        },
        options: Options(
          headers: {
            'If-Match': etag,
          },
        ),
      );

      final body = response.data;

      if (body == null) {
        throw const ServerFailure();
      }

      return AuthUser(
        id: body['id'] as String,
        email: body['email'] as String,
        firstName: body['first_name'] as String,
        lastName: body['last_name'] as String,
        role: body['role'] as String,
        createdAt: DateTime.parse(
          body['created_at'] as String,
        ),
        mustChangePassword: (body['must_change_password'] as bool?) ?? false,
        phone: body['phone'] as String?,
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(
        error,
      );
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) async {
    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/v1/devices/reset/request',
        data: {'email': email, 'password': password},
        options: Options(extra: const {DioClient.skipAuthRefreshKey: true}),
      );

      final body = response.data;
      if (body == null) {
        throw const ServerFailure();
      }

      return DeviceResetChallenge(
        challengeId: body['challenge_id'] as String,
        expiresInSeconds: body['expires_in_seconds'] as int,
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) async {
    try {
      await dio.post<void>(
        '/api/v1/devices/reset/confirm',
        data: {'challenge_id': challengeId, 'code': code},
        options: Options(extra: const {DioClient.skipAuthRefreshKey: true}),
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<int> requestPasswordReset({
    required String email,
  }) async {
    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/v1/auth/password/reset/request',
        data: {
          'email': email,
        },
        options: Options(
          extra: const {
            DioClient.skipAuthRefreshKey: true,
          },
        ),
      );

      final body = response.data;
      final expiresInSeconds = body?['expires_in_seconds'];

      if (expiresInSeconds is! int) {
        throw const ServerFailure();
      }

      return expiresInSeconds;
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<void> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    try {
      await dio.post<void>(
        '/api/v1/auth/password/reset/confirm',
        data: {
          'email': email,
          'code': code,
          'new_password': newPassword,
        },
        options: Options(
          extra: const {
            DioClient.skipAuthRefreshKey: true,
          },
        ),
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    try {
      await dio.post<void>(
        '/api/v1/auth/password/change',
        data: {
          'current_password': currentPassword,
          'new_password': newPassword,
        },
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  String _formatDate(DateTime value) {
    final year = value.year.toString().padLeft(4, '0');
    final month = value.month.toString().padLeft(2, '0');
    final day = value.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
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
        mustChangePassword: (user['must_change_password'] as bool?) ?? false,
        phone: user['phone'] as String?,
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
