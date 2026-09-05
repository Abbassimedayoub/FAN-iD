import 'dart:math';

import 'package:dio/dio.dart';

import '../../cart/domain/fan_cart.dart';
import '../../../../core/errors/failure.dart';
import '../../../../core/network/dio_client.dart';
import '../domain/fan_checkout.dart';

class FanCheckoutRemoteDataSource implements FanCheckoutRepository {
  FanCheckoutRemoteDataSource(
    this._dio, {
    String Function(String prefix)? idempotencyKeyFactory,
  }) : _idempotencyKeyFactory = idempotencyKeyFactory ?? _defaultIdempotencyKey;

  final Dio _dio;
  final String Function(String prefix) _idempotencyKeyFactory;

  static String _defaultIdempotencyKey(String prefix) {
    final random = Random.secure();
    final suffix = List<String>.generate(
      24,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();

    return '$prefix-${DateTime.now().microsecondsSinceEpoch}-$suffix';
  }

  @override
  Future<FanCheckoutSession> createCheckout(
    FanCart cart,
  ) async {
    if (cart.isEmpty) {
      throw const BusinessFailure(
        'EMPTY_CART',
        'Votre panier est vide.',
      );
    }

    try {
      final reservation = await _dio.post<Map<String, dynamic>>(
        '/api/v1/orders/reservations',
        data: <String, dynamic>{
          'items': cart.items
              .map(
                (item) => <String, dynamic>{
                  'ticket_category_id': item.ticketCategoryId,
                  'quantity': item.quantity,
                },
              )
              .toList(growable: false),
        },
        options: Options(
          headers: <String, String>{
            'Idempotency-Key': _idempotencyKeyFactory('reservation'),
          },
        ),
      );

      final orderId = reservation.data?['order_id']?.toString();
      if (orderId == null || orderId.isEmpty) {
        throw const ServerFailure();
      }

      final paymentIntent = await _dio.post<Map<String, dynamic>>(
        '/api/v1/orders/$orderId/payment-intent',
        data: <String, dynamic>{},
        options: Options(
          headers: <String, String>{
            'Idempotency-Key': _idempotencyKeyFactory('payment-intent'),
          },
        ),
      );

      final clientSecret = paymentIntent.data?['client_secret']?.toString();

      if (clientSecret == null || clientSecret.isEmpty) {
        throw const ServerFailure();
      }

      return FanCheckoutSession(
        orderId: orderId,
        paymentIntentClientSecret: clientSecret,
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }

  @override
  Future<String> readOrderStatus(String orderId) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/orders/$orderId',
      );
      final status = response.data?['status']?.toString().trim();

      if (status == null || status.isEmpty) {
        throw const ServerFailure();
      }

      return status.toUpperCase();
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }
}
