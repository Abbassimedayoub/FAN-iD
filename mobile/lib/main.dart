import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'features/auth/presentation/pages/auth_entry_page.dart';

void main() {
  runApp(const ProviderScope(child: FanIdApp()));
}

class FanIdApp extends StatelessWidget {
  const FanIdApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FAN id',
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF1663C7),
        useMaterial3: true,
      ),
      home: const AuthEntryPage(),
    );
  }
}
