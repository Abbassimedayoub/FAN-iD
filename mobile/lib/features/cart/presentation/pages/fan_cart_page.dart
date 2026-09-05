import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_stripe/flutter_stripe.dart' hide Card;

import '../../../../core/errors/failure.dart';
import '../../../checkout/presentation/providers/fan_checkout_provider.dart';
import '../../domain/fan_cart.dart';
import '../providers/fan_cart_provider.dart';

class FanCartPage extends ConsumerStatefulWidget {
  const FanCartPage({
    required this.cartOwnerKey,
    super.key,
  });

  final String cartOwnerKey;

  @override
  ConsumerState<FanCartPage> createState() => _FanCartPageState();
}

class _FanCartPageState extends ConsumerState<FanCartPage> {
  bool _paymentInProgress = false;

  @override
  Widget build(
    BuildContext context,
  ) {
    final cartState = ref.watch(
      fanCartControllerProvider(
        widget.cartOwnerKey,
      ),
    );

    final controller = ref.read(
      fanCartControllerProvider(
        widget.cartOwnerKey,
      ).notifier,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Mon panier'),
      ),
      body: SafeArea(
        child: cartState.when(
          loading: () => const Center(
            child: CircularProgressIndicator(),
          ),
          error: (error, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                'Impossible de charger '
                'le panier.\n$error',
                textAlign: TextAlign.center,
              ),
            ),
          ),
          data: (cart) {
            if (cart.isEmpty) {
              return const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Icon(
                        Icons.shopping_cart_outlined,
                        size: 64,
                      ),
                      SizedBox(height: 16),
                      Text(
                        'Votre panier est vide.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              );
            }

            return ListView(
              padding: const EdgeInsets.all(16),
              children: <Widget>[
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(
                      16,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          '${cart.totalQuantity} '
                          'billet(s)',
                          style: Theme.of(
                            context,
                          ).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                        const SizedBox(
                          height: 6,
                        ),
                        const Text(
                          'Panier conservé 10 minutes '
                          'à partir du premier ajout.',
                        ),
                        const SizedBox(
                          height: 4,
                        ),
                        FanCartCountdown(
                          expiresAt: cart.expiresAt,
                        ),
                        const SizedBox(
                          height: 8,
                        ),
                        const Text(
                          'Les places seront '
                          'revalidées au moment '
                          'du paiement.',
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                ...cart.items.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(
                      bottom: 12,
                    ),
                    child: _CartItemCard(
                      item: item,
                      enabled: !_paymentInProgress,
                      onUpdateQuantity: (quantity) async {
                        try {
                          await controller.updateQuantity(
                            item.ticketCategoryId,
                            quantity,
                          );
                        } on FanCartValidationException catch (error) {
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  error.message,
                                ),
                              ),
                            );
                          }
                        }
                      },
                      onRemove: () async {
                        final shouldCloseCart = cart.items.length == 1;

                        await controller.removeItem(
                          item.ticketCategoryId,
                        );

                        if (shouldCloseCart && context.mounted) {
                          await Navigator.of(
                            context,
                          ).maybePop();
                        }
                      },
                    ),
                  ),
                ),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(
                      16,
                    ),
                    child: Row(
                      children: <Widget>[
                        Expanded(
                          child: Text(
                            'Total',
                            style: Theme.of(
                              context,
                            ).textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                          ),
                        ),
                        Text(
                          _formatCents(
                            cart.totalCents,
                          ),
                          key: const ValueKey<String>(
                            'fan-cart-total',
                          ),
                          style: Theme.of(
                            context,
                          ).textTheme.titleLarge?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  key: const ValueKey<String>('fan-cart-pay'),
                  onPressed:
                      _paymentInProgress ? null : () => _startPayment(cart),
                  icon: _paymentInProgress
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                          ),
                        )
                      : const Icon(Icons.payment_outlined),
                  label: Text(
                    _paymentInProgress
                        ? 'Préparation du paiement…'
                        : 'Continuer vers le paiement',
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Le paiement est confirmé par Stripe avant '
                  'la validation de votre commande.',
                  textAlign: TextAlign.center,
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Future<void> _startPayment(FanCart cart) async {
    if (_paymentInProgress) {
      return;
    }

    if (Stripe.publishableKey.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Le paiement Stripe n’est pas configuré dans cet APK.',
          ),
        ),
      );
      return;
    }

    setState(() {
      _paymentInProgress = true;
    });

    final checkout = ref.read(fanCheckoutControllerProvider.notifier);
    final cartController = ref.read(
      fanCartControllerProvider(widget.cartOwnerKey).notifier,
    );

    try {
      final session = await checkout.preparePayment(cart);

      await Stripe.instance.initPaymentSheet(
        paymentSheetParameters: SetupPaymentSheetParameters(
          merchantDisplayName: 'FAN iD',
          paymentIntentClientSecret: session.paymentIntentClientSecret,
          primaryButtonLabel: 'Payer',
          returnURL: 'fanid://stripe-redirect',
        ),
      );

      await Stripe.instance.presentPaymentSheet();

      await checkout.waitForPaid(session.orderId);
      await cartController.clearCart();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Paiement confirmé. Votre commande est validée.',
            ),
          ),
        );
        await Navigator.of(context).maybePop();
      }
    } on StripeException catch (error) {
      if (mounted) {
        final message = error.error.localizedMessage ??
            'Le paiement a été annulé ou refusé.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message)),
        );
      }
    } on Failure catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Impossible de finaliser le paiement. Réessayez plus tard.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _paymentInProgress = false;
        });
      }
    }
  }

  static String _formatCents(
    int value,
  ) {
    final euros = value ~/ 100;
    final cents = value % 100;

    if (cents == 0) {
      return '$euros €';
    }

    return '$euros,'
        '${cents.toString().padLeft(2, '0')} €';
  }
}

class FanCartCountdown extends StatefulWidget {
  const FanCartCountdown({
    required this.expiresAt,
    this.now,
    super.key,
  });

  final DateTime? expiresAt;
  final DateTime Function()? now;

  @override
  State<FanCartCountdown> createState() => _FanCartCountdownState();
}

class _FanCartCountdownState extends State<FanCartCountdown> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();

    _timer = Timer.periodic(
      const Duration(seconds: 1),
      (_) {
        if (mounted) {
          setState(() {});
        }
      },
    );
  }

  DateTime _now() {
    return widget.now?.call() ?? DateTime.now().toUtc();
  }

  int _remainingSeconds() {
    final expiresAt = widget.expiresAt;

    if (expiresAt == null) {
      return 0;
    }

    final milliseconds =
        expiresAt.toUtc().difference(_now().toUtc()).inMilliseconds;

    if (milliseconds <= 0) {
      return 0;
    }

    final seconds = (milliseconds + 999) ~/ 1000;

    if (seconds > FanCart.ttl.inSeconds) {
      return FanCart.ttl.inSeconds;
    }

    return seconds;
  }

  String _label(int totalSeconds) {
    final minutes = totalSeconds ~/ 60;
    final seconds = totalSeconds % 60;

    return '${minutes.toString().padLeft(2, '0')}:'
        '${seconds.toString().padLeft(2, '0')}';
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final remainingSeconds = _remainingSeconds();

    final progress = FanCart.ttl.inSeconds == 0
        ? 0.0
        : remainingSeconds / FanCart.ttl.inSeconds;

    return Container(
      key: const ValueKey<String>(
        'fan-cart-countdown-container',
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
      ),
      child: Column(
        children: <Widget>[
          Row(
            children: <Widget>[
              const Icon(
                Icons.timer_outlined,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Temps restant',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
              ),
              Text(
                _label(remainingSeconds),
                key: const ValueKey<String>(
                  'fan-cart-countdown',
                ),
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          LinearProgressIndicator(
            key: const ValueKey<String>(
              'fan-cart-countdown-progress',
            ),
            value: progress,
          ),
        ],
      ),
    );
  }
}

class _CartItemCard extends StatelessWidget {
  const _CartItemCard({
    required this.item,
    required this.enabled,
    required this.onUpdateQuantity,
    required this.onRemove,
  });

  final FanCartItem item;
  final bool enabled;
  final Future<void> Function(int quantity) onUpdateQuantity;
  final Future<void> Function() onRemove;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: ValueKey<String>(
        'fan-cart-item-'
        '${item.ticketCategoryId}',
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              item.eventName,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              '${item.ticketCategoryName} — '
              '${_FanCartPageState._formatCents(
                item.unitPriceCents,
              )}',
            ),
            const SizedBox(height: 4),
            Text(
              'Disponibilité au dernier '
              'chargement : '
              '${item.availableCount}',
            ),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                IconButton.outlined(
                  key: ValueKey<String>(
                    'fan-cart-decrement-'
                    '${item.ticketCategoryId}',
                  ),
                  tooltip: 'Diminuer la quantité',
                  onPressed: enabled && item.quantity > 1
                      ? () {
                          onUpdateQuantity(
                            item.quantity - 1,
                          );
                        }
                      : null,
                  icon: const Icon(Icons.remove),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 18,
                  ),
                  child: Text(
                    '${item.quantity}',
                    key: ValueKey<String>(
                      'fan-cart-quantity-'
                      '${item.ticketCategoryId}',
                    ),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                IconButton.outlined(
                  key: ValueKey<String>(
                    'fan-cart-increment-'
                    '${item.ticketCategoryId}',
                  ),
                  tooltip: 'Augmenter la quantité',
                  onPressed: enabled && item.quantity < item.availableCount
                      ? () {
                          onUpdateQuantity(
                            item.quantity + 1,
                          );
                        }
                      : null,
                  icon: const Icon(Icons.add),
                ),
                const Spacer(),
                IconButton(
                  key: ValueKey<String>(
                    'fan-cart-remove-'
                    '${item.ticketCategoryId}',
                  ),
                  tooltip: 'Supprimer du panier',
                  onPressed: enabled ? onRemove : null,
                  icon: const Icon(
                    Icons.delete_outline,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                'Sous-total : '
                '${_FanCartPageState._formatCents(
                  item.lineTotalCents,
                )}',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
