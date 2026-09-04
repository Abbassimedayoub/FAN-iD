import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/fan_cart.dart';
import '../providers/fan_cart_provider.dart';

class FanCartPage extends ConsumerWidget {
  const FanCartPage({
    required this.cartOwnerKey,
    super.key,
  });

  final String cartOwnerKey;

  @override
  Widget build(
    BuildContext context,
    WidgetRef ref,
  ) {
    final cartState = ref.watch(
      fanCartControllerProvider(
        cartOwnerKey,
      ),
    );

    final controller = ref.read(
      fanCartControllerProvider(
        cartOwnerKey,
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
                  onPressed: null,
                  icon: const Icon(
                    Icons.payment_outlined,
                  ),
                  label: const Text(
                    'Continuer vers le paiement',
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Le paiement sera branché '
                  'dans la prochaine étape.',
                  textAlign: TextAlign.center,
                ),
              ],
            );
          },
        ),
      ),
    );
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
    required this.onUpdateQuantity,
    required this.onRemove,
  });

  final FanCartItem item;
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
              '${FanCartPage._formatCents(
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
                  onPressed: item.quantity > 1
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
                  onPressed: item.quantity < item.availableCount
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
                  onPressed: onRemove,
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
                '${FanCartPage._formatCents(
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
