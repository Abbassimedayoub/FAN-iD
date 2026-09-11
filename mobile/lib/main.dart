import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'design_system/theme.dart';
import 'features/auth/presentation/pages/auth_entry_page.dart';

const _stripePublishableKey = String.fromEnvironment(
  'STRIPE_PUBLISHABLE_KEY',
);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Hive.initFlutter();

  final stripePublishableKey = _stripePublishableKey.trim();

  if (stripePublishableKey.isNotEmpty) {
    Stripe.publishableKey = stripePublishableKey;
    Stripe.urlScheme = 'fanid';
    await Stripe.instance.applySettings();
  }

  runApp(
    const ProviderScope(
      child: FanIdApp(),
    ),
  );
}

class FanIdApp extends StatelessWidget {
  const FanIdApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FAN id',
      theme: FanTheme.light,
      home: const AuthEntryPage(),
    );
  }
}
