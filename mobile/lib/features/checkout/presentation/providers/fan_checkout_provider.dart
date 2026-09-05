import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../cart/domain/fan_cart.dart';
import '../../data/fan_checkout_remote_data_source.dart';
import '../../domain/fan_checkout.dart';

class FanCheckoutController extends StateNotifier<AsyncValue<void>> {
  FanCheckoutController({
    required FanCheckoutRepository repository,
    Future<void> Function(Duration duration)? wait,
  })  : _repository = repository,
        _wait = wait ?? Future<void>.delayed,
        super(const AsyncData<void>(null));

  final FanCheckoutRepository _repository;
  final Future<void> Function(Duration duration) _wait;

  Future<FanCheckoutSession> preparePayment(
    FanCart cart,
  ) async {
    state = const AsyncLoading();

    try {
      final session = await _repository.createCheckout(cart);
      state = const AsyncData<void>(null);
      return session;
    } catch (error, stackTrace) {
      state = AsyncError<void>(error, stackTrace);
      rethrow;
    }
  }

  Future<void> waitForPaid(
    String orderId, {
    int maxAttempts = 10,
    Duration interval = const Duration(seconds: 1),
  }) async {
    state = const AsyncLoading();

    try {
      for (var attempt = 0; attempt < maxAttempts; attempt++) {
        final status = await _repository.readOrderStatus(orderId);

        if (status == 'PAID') {
          state = const AsyncData<void>(null);
          return;
        }

        if (status != 'PENDING') {
          throw BusinessFailure(
            'ORDER_NOT_PAYABLE',
            'La commande ne peut pas être confirmée.',
            details: <String, dynamic>{'status': status},
          );
        }

        if (attempt + 1 < maxAttempts) {
          await _wait(interval);
        }
      }

      throw const BusinessFailure(
        'PAYMENT_CONFIRMATION_PENDING',
        'Le paiement est en cours de confirmation. '
            'Votre panier est conservé.',
      );
    } catch (error, stackTrace) {
      state = AsyncError<void>(error, stackTrace);
      rethrow;
    }
  }
}

final fanCheckoutControllerProvider =
    StateNotifierProvider.autoDispose<FanCheckoutController, AsyncValue<void>>(
  (ref) {
    return FanCheckoutController(
      repository: FanCheckoutRemoteDataSource(
        ref.watch(dioClientProvider).dio,
      ),
    );
  },
);
