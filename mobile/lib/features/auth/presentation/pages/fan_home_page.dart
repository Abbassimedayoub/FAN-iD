import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../cart/presentation/pages/fan_cart_page.dart';
import '../../../catalog/presentation/pages/fan_catalog_page.dart';
import '../../../ticketing/presentation/pages/fan_tickets_page.dart';
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
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(18, 18, 18, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: const Color(0xFF0E2A4D),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: const Color(0x2922D3EE),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.verified_user_outlined,
                        size: 28, color: Color(0xFF7CEBFA)),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                      child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Bonjour ${user.firstName}',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(color: Colors.white),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Votre session FAN-iD est active.',
                        style: Theme.of(context)
                            .textTheme
                            .bodyMedium
                            ?.copyWith(color: const Color(0xFFAECBE8)),
                      ),
                    ],
                  )),
                ]),
              ),
              const SizedBox(height: 18),
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
                        builder: (_) => FanCatalogPage(
                          cartOwnerKey: user.email.trim().toLowerCase(),
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
              Card(
                key: const ValueKey<String>(
                  'fan-cart-card',
                ),
                child: ListTile(
                  leading: const Icon(
                    Icons.shopping_cart_outlined,
                  ),
                  title: const Text('Mon panier'),
                  subtitle: const Text(
                    'Billets sélectionnés — conservation 10 minutes.',
                  ),
                  trailing: const Icon(
                    Icons.chevron_right,
                  ),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => FanCartPage(
                          cartOwnerKey: user.email.trim().toLowerCase(),
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
              Card(
                key: const ValueKey<String>('fan-tickets-card'),
                child: ListTile(
                  leading: const Icon(Icons.confirmation_number_outlined),
                  title: const Text('Mes billets'),
                  subtitle: const Text(
                    'Consulter vos billets confirmés.',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => const FanTicketsPage(),
                      ),
                    );
                  },
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
              const SizedBox(height: 20),
              OutlinedButton.icon(
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
