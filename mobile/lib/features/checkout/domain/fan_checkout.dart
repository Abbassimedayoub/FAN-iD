import '../../cart/domain/fan_cart.dart';

class FanCheckoutSession {
  const FanCheckoutSession({
    required this.orderId,
    required this.paymentIntentClientSecret,
  });

  final String orderId;
  final String paymentIntentClientSecret;
}

abstract class FanCheckoutRepository {
  Future<FanCheckoutSession> createCheckout(
    FanCart cart,
  );

  Future<String> readOrderStatus(
    String orderId,
  );
}
