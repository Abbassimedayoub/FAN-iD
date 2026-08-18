import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'shared/widgets/state_widgets.dart';

/// Point d'entrée — coquille du Sprint 0 (§4.4/§80 master prompt) : aucun
/// écran métier, seulement la structure Clean Architecture + les fondations
/// d'état d'écran, exercées ici sur un contenu statique de démonstration.
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
        colorSchemeSeed:
            const Color(0xFF1663C7), // primary — cohérent avec les tokens web
        useMaterial3: true,
      ),
      home: const FanIdScaffold(
        title: 'FAN id — Sprint 0',
        body: Center(
            child: Text('Socle plateforme — aucune fonctionnalité métier.')),
      ),
    );
  }
}
