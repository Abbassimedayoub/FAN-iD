import 'dart:math';

import 'package:dio/dio.dart';

import '../errors/failure.dart';

/// Client Dio (§46/§4.4 Source B) : Bearer, corrélation, refresh UNIQUE mis
/// en file (même problème et même solution que le client web — voir
/// web/src/lib/httpClient.ts), timeouts 10s.
///
/// Le contenu métier du refresh est livré au Sprint 1 ; ce module ne
/// fournit que le mécanisme de verrouillage générique.
class DioClient {
  DioClient({required String baseUrl, required this.tokenProvider}) {
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
          final token = tokenProvider();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          handler.next(error);
        },
      ),
    );
  }

  late final Dio dio;
  final String? Function() tokenProvider;

  Future<String>? _refreshFuture;

  /// Verrou de refresh — une seule requête réseau à la fois, même si
  /// plusieurs appels échouent en 401 en parallèle.
  Future<String> refreshAccessTokenOnce() {
    return _refreshFuture ??= _performTokenRefresh().whenComplete(() {
      _refreshFuture = null;
    });
  }

  Future<String> _performTokenRefresh() {
    throw UnimplementedError(
      'performTokenRefresh() non implémenté au Sprint 0 — logique de '
      'rotation de refresh token livrée au Sprint 1 (identity).',
    );
  }

  String _generateCorrelationId() {
    final random = Random.secure();
    return List.generate(16, (_) => random.nextInt(16).toRadixString(16)).join();
  }
}

/// Mappe une [DioException] vers une [Failure] scellée (§4.4 Source B) —
/// le message dépend de la CLASSE d'erreur, jamais du code HTTP brut.
Failure mapDioExceptionToFailure(DioException exception) {
  final status = exception.response?.statusCode;
  if (status == null) {
    return const NetworkFailure();
  }
  if (status == 401) return const AuthFailure();
  if (status == 403) return const PermissionFailure();
  if (status == 404) return const NotFoundFailure();
  if (status >= 500) return const ServerFailure();

  final body = exception.response?.data;
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
