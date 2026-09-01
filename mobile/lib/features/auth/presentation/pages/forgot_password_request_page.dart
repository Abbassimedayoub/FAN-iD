import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

import '../mappers/password_reset_failure_mapper.dart';
import '../providers/auth_providers.dart';

class ForgotPasswordRequestPage extends ConsumerStatefulWidget {
  const ForgotPasswordRequestPage({
    required this.onRequested,
    this.onBack,
    super.key,
  });

  final ValueChanged<String> onRequested;
  final VoidCallback? onBack;

  @override
  ConsumerState<ForgotPasswordRequestPage> createState() =>
      _ForgotPasswordRequestPageState();
}

class _ForgotPasswordRequestPageState
    extends ConsumerState<ForgotPasswordRequestPage> {
  final _emailController = TextEditingController();

  bool _loading = false;
  String? _emailError;
  String? _formError;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_loading) {
      return;
    }

    final email = _emailController.text.trim();

    if (email.isEmpty || !email.contains('@')) {
      setState(() {
        _emailError = 'Saisissez une adresse e-mail valide.';
        _formError = null;
      });
      return;
    }

    setState(() {
      _loading = true;
      _emailError = null;
      _formError = null;
    });

    try {
      await ref.read(requestPasswordResetUseCaseProvider)(
        email: email,
      );

      if (!mounted) {
        return;
      }

      widget.onRequested(email);
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
                      'Mot de passe oublié ?',
                      style: FanType.h1,
                    ),
                    const SizedBox(height: FanSpacing.sm),
                    Text(
                      'Saisissez l’adresse e-mail liée à votre compte FANID.',
                      style: FanType.body.copyWith(
                        color: FanColors.textSecondary,
                      ),
                    ),
                    const SizedBox(height: FanSpacing.xl),
                    const NavyNoticeBanner(
                      icon: Icons.mark_email_read_outlined,
                      onLight: true,
                      message:
                          'Nous vous enverrons un lien sécurisé et un code à 6 chiffres valable 15 minutes.',
                    ),
                    const SizedBox(height: FanSpacing.xxl),
                    FanIdTextField(
                      label: 'Email',
                      controller: _emailController,
                      hintText: 'nom@exemple.fr',
                      enabled: !_loading,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.done,
                      autofillHints: const [
                        AutofillHints.email,
                      ],
                      errorText: _emailError,
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
                      label: 'Recevoir le lien et le code',
                      loading: _loading,
                      onPressed: submitAction,
                    ),
                    const SizedBox(height: FanSpacing.md),
                    FanIdSecondaryButton(
                      label: 'Retour à la connexion',
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
