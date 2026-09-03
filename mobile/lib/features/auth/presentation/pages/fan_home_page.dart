import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../catalog/presentation/pages/fan_catalog_page.dart';
import '../../domain/entities/login_session.dart';
import '../controllers/auth_controller.dart';
import 'account_page.dart';

class FanHomePage extends ConsumerWidget {
  const FanHomePage({required this.user, super.key});

  final AuthUser user;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FAN-iD'),
        actions: [
          IconButton(
            tooltip: 'Mon compte',
            icon: const Icon(Icons.person_outline),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => AccountPage(user: user),
                ),
              );
            },
          ),
          IconButton(
            tooltip: 'Se déconnecter',
            icon: const Icon(Icons.logout),
            onPressed: () {
              ref.read(authControllerProvider.notifier).signOutLocal();
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 32),
              const Icon(Icons.verified_user_outlined, size: 80),
              const SizedBox(height: 24),
              Text(
                'Bonjour ${user.firstName}',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 12),
              Text(
                'Votre session FAN-iD est active.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 40),
              Card(
                key: const ValueKey<String>('fan-catalog-card'),
                child: ListTile(
                  leading: const Icon(Icons.explore_outlined),
                  title: const Text('Catalogue'),
                  subtitle: const Text(
                    'Découvrir les événements par catégorie.',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => const FanCatalogPage(),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
              const Card(
                child: ListTile(
                  leading: Icon(Icons.confirmation_number_outlined),
                  title: Text('Mes billets'),
                  subtitle: Text(
                    'Le module billetterie sera disponible dans une prochaine étape.',
                  ),
                  trailing: Icon(Icons.chevron_right),
                ),
              ),
              const SizedBox(height: 12),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: const Text('Mon compte'),
                  subtitle: Text(user.email),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => AccountPage(user: user),
                      ),
                    );
                  },
                ),
              ),
              const Spacer(),
              FilledButton.icon(
                onPressed: () {
                  ref.read(authControllerProvider.notifier).signOutLocal();
                },
                icon: const Icon(Icons.logout),
                label: const Text('Se déconnecter'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
