import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/login_session.dart';
import '../controllers/auth_controller.dart';
import 'change_password_page.dart';
import 'phone_change_page.dart';
import 'scanner_leave_request_page.dart';

class AccountPage extends ConsumerWidget {
  const AccountPage({required this.user, super.key});

  final AuthUser user;

  String get _roleLabel {
    switch (user.role.toUpperCase()) {
      case 'SCANNER':
        return 'Contrôleur';
      case 'FAN':
        return 'FAN';
      case 'ORGANIZER':
        return 'Organisateur';
      case 'ADMIN':
        return 'Administrateur';
      default:
        return user.role;
    }
  }

  String get _initials {
    final first = user.firstName.trim().isEmpty ? '' : user.firstName.trim()[0];
    final last = user.lastName.trim().isEmpty ? '' : user.lastName.trim()[0];

    final value = '$first$last'.toUpperCase();

    return value.isEmpty ? '?' : value;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final liveUser = ref.watch(authControllerProvider).valueOrNull?.user;
    final displayedUser =
        liveUser != null && liveUser.id == user.id ? liveUser : user;

    final fullName = '${user.firstName.trim()} ${user.lastName.trim()}'.trim();

    return Scaffold(
      appBar: AppBar(title: const Text('Mon compte')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const SizedBox(height: 8),
            Center(
              child: CircleAvatar(
                radius: 44,
                child: Text(
                  _initials,
                  style: const TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              fullName,
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Text(
              user.email,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 12),
            Center(
              child: Chip(
                avatar: const Icon(Icons.badge_outlined, size: 18),
                label: Text(_roleLabel),
              ),
            ),
            const SizedBox(height: 30),
            Text(
              'Informations du compte',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.person_outline),
                    title: const Text('Nom'),
                    subtitle: Text(
                      fullName.isEmpty ? 'Non renseigné' : fullName,
                    ),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.email_outlined),
                    title: const Text('Adresse e-mail'),
                    subtitle: Text(user.email),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.badge_outlined),
                    title: const Text('Rôle'),
                    subtitle: Text(_roleLabel),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.phone_outlined),
                    title: const Text('Numéro de téléphone'),
                    subtitle: Text(
                      (displayedUser.phone?.trim().isEmpty ?? true)
                          ? 'Non renseigné'
                          : displayedUser.phone!.trim(),
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () async {
                      final changed = await Navigator.of(context).push<bool>(
                        MaterialPageRoute<bool>(
                          builder: (_) => PhoneChangePage(
                            user: displayedUser,
                          ),
                        ),
                      );

                      if (changed == true && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              (displayedUser.phone?.trim().isEmpty ?? true)
                                  ? 'Téléphone enregistré.'
                                  : 'Téléphone modifié après validation.',
                            ),
                          ),
                        );
                      }
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Sécurité',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            Card(
              child: ListTile(
                leading: const Icon(Icons.lock_outline),
                title: const Text('Changer le mot de passe'),
                subtitle: const Text(
                  'Modifiez le mot de passe de votre compte FAN-iD',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const ChangePasswordPage(),
                    ),
                  );
                },
              ),
            ),
            if (user.role.toUpperCase() == 'SCANNER') ...[
              const SizedBox(height: 24),
              Text(
                'Accès scanner',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 10),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.person_remove_outlined),
                  title: const Text(
                    'Demander la suppression de mon accès scanner',
                  ),
                  subtitle: const Text(
                    'L’organisateur devra accepter ou refuser votre demande',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => const ScannerLeaveRequestPage(),
                      ),
                    );
                  },
                ),
              ),
            ],
            const SizedBox(height: 30),
            OutlinedButton.icon(
              onPressed: () async {
                await ref.read(authControllerProvider.notifier).signOutLocal();

                if (context.mounted) {
                  Navigator.of(context).popUntil((route) => route.isFirst);
                }
              },
              icon: const Icon(Icons.logout),
              label: const Text('Se déconnecter'),
            ),
          ],
        ),
      ),
    );
  }
}
