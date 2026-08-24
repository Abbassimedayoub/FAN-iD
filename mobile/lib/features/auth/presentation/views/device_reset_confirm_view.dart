import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

class DeviceResetConfirmView extends StatelessWidget {
  const DeviceResetConfirmView({
    required this.codeController,
    required this.onSubmit,
    this.expiresInSeconds,
    this.isLoading = false,
    this.errorText,
    this.onBack,
    super.key,
  });

  final TextEditingController codeController;
  final VoidCallback onSubmit;
  final int? expiresInSeconds;
  final bool isLoading;
  final String? errorText;
  final VoidCallback? onBack;

  @override
  Widget build(BuildContext context) {
    final submitAction = isLoading ? null : onSubmit;

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
              Text('Vérifiez votre code', style: FanType.h1),
              const SizedBox(height: FanSpacing.sm),
              Text(
                'Saisissez le code reçu pour confirmer la réinitialisation '
                'de l’appareil associé.',
                style: FanType.body.copyWith(
                  color: FanColors.textSecondary,
                ),
              ),
              if (expiresInSeconds != null) ...<Widget>[
                const SizedBox(height: FanSpacing.md),
                Text(
                  'Le code expire dans $expiresInSeconds secondes.',
                  style: FanType.caption.copyWith(
                    color: FanColors.textSecondary,
                  ),
                ),
              ],
              const SizedBox(height: FanSpacing.xxl),
              FanIdTextField(
                label: 'Code de vérification',
                controller: codeController,
                enabled: !isLoading,
                errorText: errorText,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                onSubmitted:
                    submitAction == null ? null : (_) => submitAction(),
              ),
              const SizedBox(height: FanSpacing.xl),
              FanIdPrimaryButton(
                label: 'Confirmer la réinitialisation',
                loading: isLoading,
                onPressed: submitAction,
              ),
              const SizedBox(height: FanSpacing.md),
              FanIdSecondaryButton(
                label: 'Retour',
                onPressed: isLoading ? null : onBack,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
