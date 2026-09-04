import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/cart/presentation/pages/fan_cart_page.dart';

void main() {
  testWidgets(
    'affiche un compte à rebours de 10 minutes vers zéro',
    (tester) async {
      var now = DateTime.utc(
        2026,
        9,
        4,
        20,
      );

      final expiresAt = now.add(
        const Duration(minutes: 10),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FanCartCountdown(
              expiresAt: expiresAt,
              now: () => now,
            ),
          ),
        ),
      );

      expect(
        find.text('Temps restant'),
        findsOneWidget,
      );

      expect(
        find.text('10:00'),
        findsOneWidget,
      );

      var progress = tester.widget<LinearProgressIndicator>(
        find.byKey(
          const ValueKey<String>(
            'fan-cart-countdown-progress',
          ),
        ),
      );

      expect(progress.value, 1.0);

      now = now.add(
        const Duration(
          minutes: 1,
          seconds: 1,
        ),
      );

      await tester.pump(
        const Duration(seconds: 1),
      );

      expect(
        find.text('08:59'),
        findsOneWidget,
      );

      now = expiresAt;

      await tester.pump(
        const Duration(seconds: 1),
      );

      expect(
        find.text('00:00'),
        findsOneWidget,
      );

      progress = tester.widget<LinearProgressIndicator>(
        find.byKey(
          const ValueKey<String>(
            'fan-cart-countdown-progress',
          ),
        ),
      );

      expect(progress.value, 0.0);
    },
  );
}
