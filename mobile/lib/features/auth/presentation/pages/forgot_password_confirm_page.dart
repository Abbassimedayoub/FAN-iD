import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

import '../mappers/password_reset_failure_mapper.dart';
import '../providers/auth_providers.dart';

class ForgotPasswordConfirmPage extends ConsumerStatefulWidget {
  const ForgotPasswordConfirmPage({
    required this.email,
    required this.onCompleted,
    this.onBack,
    super.key,
  });

  final String email;
  final VoidCallback onCompleted;
  final VoidCallback? onBack;

  @override
  ConsumerState<ForgotPasswordConfirmPage> createState() =>
      _ForgotPasswordConfirmPageState();
}

class _ForgotPasswordConfirmPageState
    extends ConsumerState<ForgotPasswordConfirmPage> {
  final _codeController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmationController = TextEditingController();

  bool _loading = false;
  String? _codeError;
  String? _passwordError;
  String? _confirmationError;
  String? _formError;

  @override
  void dispose() {
    _codeController.dispose();
    _passwordController.dispose();
    _confirmationController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_loading) {
      return;
    }

    final code = _codeController.text.trim();
    final password = _passwordController.text;
    final confirmation = _confirmationController.text;

    String? codeError;
    String? passwordError;
    String? confirmationError;

    if (!RegExp(r'^\d{6}$').hasMatch(code)) {
      codeError = 'Le code doit contenir exactement 6 chiffres.';
    }

    if (password.length < 10) {
      passwordError = 'Utilisez au moins 10 caractères.';
    } else if (RegExp(r'^\d+$').hasMatch(password)) {
      passwordError =
          'Le mot de passe ne peut pas contenir uniquement des chiffres.';
    }

    if (password != confirmation) {
      confirmationError = 'Les deux mots de passe ne correspondent pas.';
    }

    if (codeError != null ||
        passwordError != null ||
        confirmationError != null) {
      setState(() {
        _codeError = codeError;
        _passwordError = passwordError;
        _confirmationError = confirmationError;
        _formError = null;
      });
      return;
    }

    setState(() {
      _loading = true;
      _codeError = null;
      _passwordError = null;
      _confirmationError = null;
      _formError = null;
    });

    try {
      await ref.read(confirmPasswordResetUseCaseProvider)(
        email: widget.email,
        code: code,
        newPassword: password,
      );

      if (!mounted) {
        return;
      }

      widget.onCompleted();
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _formError = mapPasswordResetFailure(error);
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final VoidCallback? submitAction = _loading ? null : _submit;

    return Scaffold(
      backgroundColor: FanColors.background,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              padding: const EdgeInsets.symmetric(
                horizontal: FanSpacing.screenH,
                vertical: FanSpacing.xxl,
              ),
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: constraints.maxHeight - FanSpacing.xxl * 2,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const FanIdLogo(size: 64),
                    const SizedBox(height: FanSpacing.xxl),
                    Text(
                      'Vérifiez votre e-mail',
                      style: FanType.h1,
                    ),
                    const SizedBox(height: FanSpacing.sm),
                    Text(
                      'Saisissez le code reçu puis créez votre nouveau mot de passe.',
                      style: FanType.body.copyWith(
                        color: FanColors.textSecondary,
                      ),
                    ),
                    const SizedBox(height: FanSpacing.xl),
                    NavyNoticeBanner(
                      icon: Icons.shield_outlined,
                      onLight: true,
                      message:
                          'Si un compte correspond à ${widget.email}, le code reçu est valable 15 minutes et une seule fois.',
                    ),
                    const SizedBox(height: FanSpacing.xxl),
                    FanIdTextField(
                      label: 'Code à 6 chiffres',
                      controller: _codeController,
                      hintText: '000000',
                      enabled: !_loading,
                      keyboardType: TextInputType.number,
                      textInputAction: TextInputAction.next,
                      autofillHints: const [
                        AutofillHints.oneTimeCode,
                      ],
                      errorText: _codeError,
                    ),
                    const SizedBox(height: FanSpacing.lg),
                    FanIdTextField(
                      label: 'Nouveau mot de passe',
                      controller: _passwordController,
                      obscure: true,
                      enabled: !_loading,
                      textInputAction: TextInputAction.next,
                      autofillHints: const [
                        AutofillHints.newPassword,
                      ],
                      errorText: _passwordError,
                    ),
                    const SizedBox(height: FanSpacing.lg),
                    FanIdTextField(
                      label: 'Confirmer le mot de passe',
                      controller: _confirmationController,
                      obscure: true,
                      enabled: !_loading,
                      textInputAction: TextInputAction.done,
                      autofillHints: const [
                        AutofillHints.newPassword,
                      ],
                      errorText: _confirmationError,
                      onSubmitted:
                          submitAction == null ? null : (_) => submitAction(),
                    ),
                    if (_formError != null) ...[
                      const SizedBox(height: FanSpacing.md),
                      Semantics(
                        liveRegion: true,
                        child: Text(
                          _formError!,
                          style: FanType.body.copyWith(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: FanSpacing.xl),
                    FanIdPrimaryButton(
                      label: 'Enregistrer le nouveau mot de passe',
                      loading: _loading,
                      onPressed: submitAction,
                    ),
                    const SizedBox(height: FanSpacing.md),
                    FanIdSecondaryButton(
                      label: 'Recevoir un nouveau code',
                      onPressed: _loading ? null : widget.onBack,
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
