import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

class RegisterView extends StatelessWidget {
  const RegisterView({
    required this.firstNameController,
    required this.lastNameController,
    required this.emailController,
    required this.passwordController,
    required this.dateOfBirth,
    required this.termsAccepted,
    required this.onPickDate,
    required this.onTermsChanged,
    required this.onSubmit,
    this.phoneController,
    this.isLoading = false,
    this.errorText,
    this.onBackToLogin,
    super.key,
  });

  final TextEditingController firstNameController;
  final TextEditingController lastNameController;
  final TextEditingController emailController;
  final TextEditingController passwordController;
  final TextEditingController? phoneController;

  final DateTime? dateOfBirth;
  final bool termsAccepted;
  final bool isLoading;
  final String? errorText;

  final VoidCallback onPickDate;
  final ValueChanged<bool> onTermsChanged;
  final VoidCallback onSubmit;
  final VoidCallback? onBackToLogin;

  String get _dateLabel {
    final value = dateOfBirth;
    if (value == null) {
      return 'Sélectionner une date';
    }

    final day = value.day.toString().padLeft(2, '0');
    final month = value.month.toString().padLeft(2, '0');
    return '$day/$month/${value.year}';
  }

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
              Text('Créer votre compte', style: FanType.h1),
              const SizedBox(height: FanSpacing.sm),
              Text(
                'Rejoignez FANID pour accéder à vos billets sécurisés.',
                style: FanType.body.copyWith(
                  color: FanColors.textSecondary,
                ),
              ),
              const SizedBox(height: FanSpacing.xxl),
              FanIdTextField(
                label: 'Prénom',
                controller: firstNameController,
                enabled: !isLoading,
                textInputAction: TextInputAction.next,
                autofillHints: const <String>[AutofillHints.givenName],
              ),
              const SizedBox(height: FanSpacing.lg),
              FanIdTextField(
                label: 'Nom',
                controller: lastNameController,
                enabled: !isLoading,
                textInputAction: TextInputAction.next,
                autofillHints: const <String>[AutofillHints.familyName],
              ),
              const SizedBox(height: FanSpacing.lg),
              FanIdTextField(
                label: 'Email',
                controller: emailController,
                hintText: 'nom@exemple.fr',
                enabled: !isLoading,
                keyboardType: TextInputType.emailAddress,
                textInputAction: TextInputAction.next,
                autofillHints: const <String>[AutofillHints.email],
              ),
              const SizedBox(height: FanSpacing.lg),
              FanIdTextField(
                label: 'Mot de passe',
                controller: passwordController,
                obscure: true,
                enabled: !isLoading,
                textInputAction: TextInputAction.next,
                autofillHints: const <String>[AutofillHints.newPassword],
              ),
              if (phoneController != null) ...<Widget>[
                const SizedBox(height: FanSpacing.lg),
                FanIdTextField(
                  label: 'Téléphone (facultatif)',
                  controller: phoneController,
                  enabled: !isLoading,
                  keyboardType: TextInputType.phone,
                  textInputAction: TextInputAction.next,
                  autofillHints: const <String>[AutofillHints.telephoneNumber],
                ),
              ],
              const SizedBox(height: FanSpacing.lg),
              Text('Date de naissance', style: FanType.label),
              const SizedBox(height: FanSpacing.sm),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: isLoading ? null : onPickDate,
                  icon: const Icon(Icons.calendar_today_outlined),
                  label: Text(_dateLabel),
                ),
              ),
              const SizedBox(height: FanSpacing.md),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: termsAccepted,
                onChanged: isLoading
                    ? null
                    : (value) => onTermsChanged(value ?? false),
                controlAffinity: ListTileControlAffinity.leading,
                title: Text(
                  'J’accepte les conditions générales.',
                  style: FanType.body,
                ),
              ),
              if (errorText != null) ...<Widget>[
                const SizedBox(height: FanSpacing.sm),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    errorText!,
                    style: FanType.body.copyWith(color: FanColors.danger),
                  ),
                ),
              ],
              const SizedBox(height: FanSpacing.xl),
              FanIdPrimaryButton(
                label: 'Créer mon compte',
                loading: isLoading,
                onPressed: submitAction,
              ),
              const SizedBox(height: FanSpacing.lg),
              Align(
                alignment: Alignment.center,
                child: FanIdLinkButton(
                  label: 'J’ai déjà un compte',
                  onPressed: isLoading ? null : onBackToLogin,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
