import 'dart:math';

import 'package:dio/dio.dart';

import '../errors/failure.dart';

/// Client Dio : Bearer, corrélation et refresh unique mis en file.
class DioClient {
  static const skipAuthRefreshKey = 'fanid_skip_auth_refresh';
  static const _retriedKey = 'fanid_auth_retried';

  static const _invalidSessionCodes = <String>{
    'TOKEN_INVALID',
    'TOKEN_REUSE_DETECTED',
    'DEVICE_MISMATCH',
    'NOT_AUTHENTICATED',
    'SESSION_INVALID',
    'SESSION_REVOKED',
  };

  DioClient({
    required String baseUrl,
    required this.tokenProvider,
    required this.refreshHandler,
    this.onRefreshFailure,
  }) {
    dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
      ),
    );

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          options.headers['X-Correlation-ID'] = _generateCorrelationId();

          final skipRefresh = options.extra[skipAuthRefreshKey] == true;
          final retried = options.extra[_retriedKey] == true;
          if (!skipRefresh && !retried) {
            final token = tokenProvider();
            if (token != null) {
              options.headers['Authorization'] = 'Bearer $token';
            }
          }

          handler.next(options);
        },
        onError: (error, handler) async {
          final options = error.requestOptions;
          final status = error.response?.statusCode;

          if (options.extra[skipAuthRefreshKey] == true) {
            handler.next(error);
            return;
          }

          if (_isExplicitInvalidSession(error)) {
            await _notifyAuthFailureOnce();
            handler.next(error);
            return;
          }

          if (status != 401) {
            handler.next(error);
            return;
          }

          if (options.extra[_retriedKey] == true) {
            await _notifyAuthFailureOnce();
            handler.next(error);
            return;
          }

          options.extra[_retriedKey] = true;

          late final String newToken;
          try {
            newToken = await refreshAccessTokenOnce();
          } catch (_) {
            handler.next(error);
            return;
          }

          options.headers['Authorization'] = 'Bearer $newToken';

          try {
            final response = await dio.fetch<dynamic>(options);
            handler.resolve(response);
          } on DioException catch (retryError) {
            // dio.fetch repasse le retry dans cet intercepteur avec
            // _retried=true. Ce passage declenche deja le nettoyage global
            // en cas de second 401. Ne pas le declencher une seconde fois ici.
            handler.next(retryError);
          }
        },
      ),
    );
  }

  late final Dio dio;
  final String? Function() tokenProvider;
  final Future<String> Function() refreshHandler;
  final Future<void> Function()? onRefreshFailure;

  Future<String>? _refreshFuture;
  Future<void>? _authFailureFuture;

  Future<String> refreshAccessTokenOnce() {
    return _refreshFuture ??= _performTokenRefresh().whenComplete(() {
      _refreshFuture = null;
    });
  }

  Future<String> _performTokenRefresh() async {
    try {
      return await refreshHandler();
    } on AuthFailure {
      await _notifyAuthFailureOnce();
      rethrow;
    }
  }

  Future<void> _notifyAuthFailureOnce() {
    final running = _authFailureFuture;
    if (running != null) {
      return running;
    }

    final callback = onRefreshFailure;
    if (callback == null) {
      return Future<void>.value();
    }

    late final Future<void> future;
    future = Future<void>.sync(callback).whenComplete(() {
      if (identical(_authFailureFuture, future)) {
        _authFailureFuture = null;
      }
    });

    _authFailureFuture = future;
    return future;
  }

  static bool _isExplicitInvalidSession(DioException error) {
    if (error.response?.statusCode != 403) {
      return false;
    }

    final body = error.response?.data;
    if (body is! Map || body['error'] is! Map) {
      return false;
    }

    final code = (body['error'] as Map)['code'];
    return code is String && _invalidSessionCodes.contains(code);
  }

  String _generateCorrelationId() {
    final random = Random.secure();
    return List.generate(16, (_) => random.nextInt(16).toRadixString(16))
        .join();
  }
}

/// Mappe une [DioException] vers une [Failure].
Failure mapDioExceptionToFailure(DioException exception) {
  final status = exception.response?.statusCode;
  if (status == null) {
    return const NetworkFailure();
  }

  final body = exception.response?.data;

  if (status == 403 && body is Map && body['error'] is Map) {
    final error = body['error'] as Map;
    final code = error['code'];

    if (code == 'DEVICE_LOCKED') {
      return BusinessFailure(
        'DEVICE_LOCKED',
        (error['message'] as String?) ?? 'Appareil déjà lié',
        details:
            (error['details'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
    }

    if (code is String && DioClient._invalidSessionCodes.contains(code)) {
      return const AuthFailure();
    }
  }

  if (status == 401) return const AuthFailure();
  if (status == 403) return const PermissionFailure();
  if (status == 404) return const NotFoundFailure();
  if (status >= 500) return const ServerFailure();

  if (body is Map && body['error'] is Map) {
    final error = body['error'] as Map;
    return BusinessFailure(
      (error['code'] as String?) ?? 'UNKNOWN_ERROR',
      (error['message'] as String?) ?? 'Erreur inconnue',
      details: (error['details'] as Map?)?.cast<String, dynamic>() ?? const {},
    );
  }

  return const ServerFailure();
}
