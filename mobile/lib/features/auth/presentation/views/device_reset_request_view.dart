import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

class DeviceResetRequestView extends StatelessWidget {
  const DeviceResetRequestView({
    required this.emailController,
    required this.passwordController,
    required this.onSubmit,
    this.isLoading = false,
    this.errorText,
    this.onBack,
    super.key,
  });

  final TextEditingController emailController;
  final TextEditingController passwordController;
  final VoidCallback onSubmit;
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
              Text('Réinitialiser votre appareil', style: FanType.h1),
              const SizedBox(height: FanSpacing.sm),
              Text(
                'Confirmez vos identifiants pour recevoir un code de '
                'vérification.',
                style: FanType.body.copyWith(
                  color: FanColors.textSecondary,
                ),
              ),
              const SizedBox(height: FanSpacing.xxl),
              FanIdTextField(
                label: 'Email',
                controller: emailController,
                enabled: !isLoading,
                keyboardType: TextInputType.emailAddress,
                textInputAction: TextInputAction.next,
                autofillHints: const <String>[AutofillHints.username],
              ),
              const SizedBox(height: FanSpacing.lg),
              FanIdTextField(
                label: 'Mot de passe',
                controller: passwordController,
                obscure: true,
                enabled: !isLoading,
                errorText: errorText,
                textInputAction: TextInputAction.done,
                autofillHints: const <String>[AutofillHints.password],
                onSubmitted:
                    submitAction == null ? null : (_) => submitAction(),
              ),
              const SizedBox(height: FanSpacing.xl),
              FanIdPrimaryButton(
                label: 'Recevoir le code',
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
