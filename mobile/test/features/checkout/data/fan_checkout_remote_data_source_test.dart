import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/cart/domain/fan_cart.dart';
import 'package:fanid_mobile/features/checkout/data/fan_checkout_remote_data_source.dart';

FanCart cartWithOneTicket() {
  return FanCart(
    items: const <FanCartItem>[
      FanCartItem(
        eventId: 'event-1',
        eventName: 'Finale',
        ticketCategoryId: 'category-1',
        ticketCategoryName: 'Standard',
        unitPriceCents: 2400,
        quantity: 2,
        availableCount: 10,
        eventCapacityTotal: 100,
      ),
    ],
    expiresAt: DateTime.utc(2026, 9, 11, 12),
  );
}

Dio checkoutDio({
  Map<String, dynamic>? reservation,
  Map<String, dynamic>? paymentIntent,
  Map<String, dynamic>? order,
  int? errorStatus,
}) {
  final dio = Dio(BaseOptions(baseUrl: 'http://127.0.0.1:8000'));

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        if (errorStatus != null) {
          handler.reject(
            DioException.badResponse(
              statusCode: errorStatus,
              requestOptions: options,
              response: Response<Map<String, dynamic>>(
                requestOptions: options,
                statusCode: errorStatus,
                data: <String, dynamic>{'code': 'FAILED'},
              ),
            ),
          );
          return;
        }

        if (options.path == '/api/v1/orders/reservations') {
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 201,
              data: reservation ?? <String, dynamic>{'order_id': 'order-1'},
            ),
          );
          return;
        }

        if (options.path == '/api/v1/orders/order-1/payment-intent') {
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 201,
              data: paymentIntent ??
                  <String, dynamic>{'client_secret': 'test-client-secret'},
            ),
          );
          return;
        }

        if (options.path == '/api/v1/orders/order-1') {
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: order ?? <String, dynamic>{'status': ' paid '},
            ),
          );
          return;
        }

        handler.reject(
          DioException(
            requestOptions: options,
            type: DioExceptionType.unknown,
          ),
        );
      },
    ),
  );

  return dio;
}

void main() {
  test('creates reservation and payment intent with stable idempotency keys',
      () async {
    final prefixes = <String>[];
    final source = FanCheckoutRemoteDataSource(
      checkoutDio(),
      idempotencyKeyFactory: (prefix) {
        prefixes.add(prefix);
        return 'test-$prefix-key';
      },
    );

    final session = await source.createCheckout(cartWithOneTicket());

    expect(session.orderId, 'order-1');
    expect(session.paymentIntentClientSecret, 'test-client-secret');
    expect(prefixes, <String>['reservation', 'payment-intent']);
  });

  test('rejects an empty cart before any request', () async {
    final source = FanCheckoutRemoteDataSource(checkoutDio());

    await expectLater(
      source.createCheckout(FanCart.empty()),
      throwsA(isA<BusinessFailure>()),
    );
  });

  test('rejects a reservation response without order id', () async {
    final source = FanCheckoutRemoteDataSource(
      checkoutDio(reservation: <String, dynamic>{}),
    );

    await expectLater(
      source.createCheckout(cartWithOneTicket()),
      throwsA(isA<ServerFailure>()),
    );
  });

  test('rejects a payment response without client secret', () async {
    final source = FanCheckoutRemoteDataSource(
      checkoutDio(paymentIntent: <String, dynamic>{}),
    );

    await expectLater(
      source.createCheckout(cartWithOneTicket()),
      throwsA(isA<ServerFailure>()),
    );
  });

  test('normalizes the backend order status', () async {
    final source = FanCheckoutRemoteDataSource(checkoutDio());

    expect(await source.readOrderStatus('order-1'), 'PAID');
  });

  test('rejects an order response without a status', () async {
    final source = FanCheckoutRemoteDataSource(
      checkoutDio(order: <String, dynamic>{}),
    );

    await expectLater(
      source.readOrderStatus('order-1'),
      throwsA(isA<ServerFailure>()),
    );
  });

  test('maps HTTP failures through the shared Dio failure mapper', () async {
    final source = FanCheckoutRemoteDataSource(checkoutDio(errorStatus: 500));

    await expectLater(
      source.readOrderStatus('order-1'),
      throwsA(isA<ServerFailure>()),
    );
  });
}
