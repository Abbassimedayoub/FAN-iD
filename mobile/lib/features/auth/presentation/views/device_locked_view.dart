import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

class DeviceLockedView extends StatelessWidget {
  const DeviceLockedView({
    required this.resetAvailable,
    this.activeDeviceLabel,
    this.boundAtText,
    this.onReset,
    this.onBackToLogin,
    super.key,
  });

  final String? activeDeviceLabel;
  final String? boundAtText;
  final bool resetAvailable;
  final VoidCallback? onReset;
  final VoidCallback? onBackToLogin;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: FanColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(
            horizontal: FanSpacing.screenH,
            vertical: FanSpacing.xxl,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const FanIdLogo(size: 64),
              const SizedBox(height: FanSpacing.xxl),
              const Icon(
                Icons.phonelink_lock_outlined,
                size: 48,
                color: FanColors.primary,
              ),
              const SizedBox(height: FanSpacing.lg),
              Text(
                'Compte lié à un autre appareil',
                style: FanType.h1,
              ),
              const SizedBox(height: FanSpacing.sm),
              Text(
                'Pour protéger vos billets contre la fraude, votre compte '
                'FANID ne peut être associé qu’à un seul appareil.',
                style: FanType.body.copyWith(
                  color: FanColors.textSecondary,
                ),
              ),
              if (activeDeviceLabel != null) ...<Widget>[
                const SizedBox(height: FanSpacing.xl),
                Text('Appareil actuellement associé', style: FanType.caption),
                const SizedBox(height: FanSpacing.xs),
                Text(activeDeviceLabel!, style: FanType.h3),
              ],
              if (boundAtText != null) ...<Widget>[
                const SizedBox(height: FanSpacing.sm),
                Text(
                  'Associé le $boundAtText',
                  style: FanType.body.copyWith(
                    color: FanColors.textSecondary,
                  ),
                ),
              ],
              const SizedBox(height: FanSpacing.xxl),
              FanIdPrimaryButton(
                label: 'Réinitialiser l’appareil associé',
                onPressed: resetAvailable ? onReset : null,
              ),
              if (!resetAvailable) ...<Widget>[
                const SizedBox(height: FanSpacing.md),
                Text(
                  'La réinitialisation de l’appareil n’est pas disponible.',
                  style: FanType.body.copyWith(
                    color: FanColors.textSecondary,
                  ),
                ),
              ],
              const SizedBox(height: FanSpacing.md),
              FanIdSecondaryButton(
                label: 'Retour à la connexion',
                onPressed: onBackToLogin,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
