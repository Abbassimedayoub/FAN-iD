import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/cart/domain/fan_cart.dart';
import 'package:fanid_mobile/features/checkout/domain/fan_checkout.dart';
import 'package:fanid_mobile/features/checkout/presentation/providers/fan_checkout_provider.dart';

class FakeCheckoutRepository implements FanCheckoutRepository {
  FakeCheckoutRepository({
    required this.session,
    required this.statuses,
  });

  final FanCheckoutSession session;
  final List<String> statuses;
  final List<FanCart> receivedCarts = <FanCart>[];
  int _statusIndex = 0;

  @override
  Future<FanCheckoutSession> createCheckout(FanCart cart) async {
    receivedCarts.add(cart);
    return session;
  }

  @override
  Future<String> readOrderStatus(String orderId) async {
    final index =
        _statusIndex < statuses.length ? _statusIndex : statuses.length - 1;
    _statusIndex++;
    return statuses[index];
  }
}

FanCart sampleCart() {
  return FanCart(
    items: const <FanCartItem>[
      FanCartItem(
        eventId: 'event-1',
        eventName: 'Concert',
        ticketCategoryId: 'tariff-1',
        ticketCategoryName: 'Standard',
        unitPriceCents: 1200,
        quantity: 2,
        availableCount: 10,
        eventCapacityTotal: 100,
      ),
    ],
    expiresAt: DateTime.utc(2026, 9, 6),
  );
}

void main() {
  test('prépare une session de paiement à partir du panier', () async {
    final repository = FakeCheckoutRepository(
      session: const FanCheckoutSession(
        orderId: 'order-1',
        paymentIntentClientSecret: 'pi_secret',
      ),
      statuses: const <String>['PENDING'],
    );
    final controller = FanCheckoutController(
      repository: repository,
      wait: (_) async {},
    );

    final session = await controller.preparePayment(sampleCart());

    expect(session.orderId, 'order-1');
    expect(repository.receivedCarts, hasLength(1));
    expect(controller.state, const AsyncData<void>(null));
  });

  test('attend le statut PAID validé par le backend', () async {
    final repository = FakeCheckoutRepository(
      session: const FanCheckoutSession(
        orderId: 'order-1',
        paymentIntentClientSecret: 'pi_secret',
      ),
      statuses: const <String>['PENDING', 'PAID'],
    );
    final controller = FanCheckoutController(
      repository: repository,
      wait: (_) async {},
    );

    await controller.waitForPaid(
      'order-1',
      maxAttempts: 2,
    );

    expect(controller.state, const AsyncData<void>(null));
  });

  test('conserve le panier si la confirmation reste en attente', () async {
    final repository = FakeCheckoutRepository(
      session: const FanCheckoutSession(
        orderId: 'order-1',
        paymentIntentClientSecret: 'pi_secret',
      ),
      statuses: const <String>['PENDING'],
    );
    final controller = FanCheckoutController(
      repository: repository,
      wait: (_) async {},
    );

    await expectLater(
      controller.waitForPaid(
        'order-1',
        maxAttempts: 1,
      ),
      throwsA(
        isA<BusinessFailure>().having(
          (failure) => failure.code,
          'code',
          'PAYMENT_CONFIRMATION_PENDING',
        ),
      ),
    );
  });
}
