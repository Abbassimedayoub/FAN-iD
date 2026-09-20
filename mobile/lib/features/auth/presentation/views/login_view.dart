import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

/// FAN-04 · Connexion — **vue visuelle pilotee de l exterieur**.
///
/// ## Contrat
///
/// This view owns no business state. It receives everything it displays and
/// reports user actions back to its caller.
///
/// ```dart
/// LoginView(
///   emailController: _email,
///   passwordController: _password,
///   isLoading: state.isLoading,
///   errorText: mapLoginFailure(state),   // deja traduit en francais
///   noticeText: sessionExpired ? LoginView.sessionExpiredNotice : null,
///   onSubmit: () => ref.read(authControllerProvider.notifier)
///       .login(_email.text, _password.text),
///   onForgotPassword: …,
///   onRegister: …,
/// )
/// ```
///
/// It imports no Riverpod, go_router, or controller dependency, so it remains
/// testable without provider or router setup.
///
/// ## Three invariants enforced by the view
///
/// 1. **The button is truly inert while [isLoading]**: `onPressed` is null,
///    rather than only changing appearance.
/// 2. **Keyboard submission respects [isLoading]**: `onSubmitted` is null on
///    the password field, preventing duplicate submission via Enter.
/// 3. **No machine error code is rendered**: [errorText] is already-localized
///    presentation text; failure-code mapping belongs to the caller.
class LoginView extends StatelessWidget {
  const LoginView({
    required this.emailController,
    required this.passwordController,
    required this.onSubmit,
    this.isLoading = false,
    this.errorText,
    this.noticeText,
    this.onForgotPassword,
    this.onRegister,
    super.key,
  });

  final TextEditingController emailController;
  final TextEditingController passwordController;

  /// Trigger submission; the view does not know what the action performs.
  final VoidCallback onSubmit;

  /// Soumission en cours : bouton inerte + indicateur, touche Entree
  /// neutralisee.
  final bool isLoading;

  /// Already-localized error message displayed below the password field.
  final String? errorText;

  /// Bandeau d information en haut du formulaire — par exemple
  /// [sessionExpiredNotice] apres un echec de rafraichissement.
  ///
  /// It does not replace the permanent device-binding notice shown by the design.
  final String? noticeText;

  final VoidCallback? onForgotPassword;
  final VoidCallback? onRegister;

  /// Message to pass in [noticeText] after session expiration.
  static const String sessionExpiredNotice =
      'Votre session a expiré. Reconnectez-vous pour accéder à vos billets.';

  /// Permanent notice from the FAN-04 design.
  static const String deviceBindingNotice =
      'Votre compte est lié à un seul appareil pour protéger vos billets '
      'contre la fraude.';

  @override
  Widget build(BuildContext context) {
    // One source of truth determines whether submission is allowed; both the
    // button and Enter-key path use it.
    final VoidCallback? submitAction = isLoading ? null : onSubmit;

    return Scaffold(
      backgroundColor: FanColors.background,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (BuildContext context, BoxConstraints constraints) {
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
                  children: <Widget>[
                    const FanIdLogo(size: 64),
                    const SizedBox(height: FanSpacing.xxl),
                    if (noticeText != null) ...<Widget>[
                      Semantics(
                        liveRegion: true,
                        child: NavyNoticeBanner(
                          icon: Icons.info_outline,
                          onLight: true,
                          message: noticeText!,
                        ),
                      ),
                      const SizedBox(height: FanSpacing.xl),
                    ],
                    Text('Bon retour !', style: FanType.h1),
                    const SizedBox(height: FanSpacing.sm),
                    Text(
                      'Connectez-vous pour accéder à vos billets sécurisés.',
                      style: FanType.body.copyWith(
                        color: FanColors.textSecondary,
                      ),
                    ),
                    const SizedBox(height: FanSpacing.xxl),
                    FanIdTextField(
                      label: 'Email',
                      controller: emailController,
                      hintText: 'nom@exemple.fr',
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
                      // Null while loading so the Enter key is truly disabled,
                      // not only the visible button.
                      onSubmitted:
                          submitAction == null ? null : (_) => submitAction(),
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: FanIdLinkButton(
                        label: 'Mot de passe oublié ?',
                        onPressed: isLoading ? null : onForgotPassword,
                      ),
                    ),
                    const SizedBox(height: FanSpacing.sm),
                    FanIdPrimaryButton(
                      label: 'Se connecter',
                      loading: isLoading,
                      onPressed: submitAction,
                    ),
                    const SizedBox(height: FanSpacing.xl),
                    const _OrSeparator(),
                    const SizedBox(height: FanSpacing.xl),
                    Align(
                      alignment: Alignment.center,
                      child: Wrap(
                        alignment: WrapAlignment.center,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: <Widget>[
                          Text('Nouveau sur FANID ?', style: FanType.body),
                          const SizedBox(width: FanSpacing.xs),
                          FanIdLinkButton(
                            label: 'Créer un compte',
                            onPressed: isLoading ? null : onRegister,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: FanSpacing.xl),
                    const NavyNoticeBanner(
                      icon: Icons.lock_outline,
                      onLight: true,
                      message: deviceBindingNotice,
                    ),
                    const SizedBox(height: FanSpacing.lg),
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

class _OrSeparator extends StatelessWidget {
  const _OrSeparator();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        const Expanded(child: Divider()),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: FanSpacing.md),
          child: Text('ou', style: FanType.caption),
        ),
        const Expanded(child: Divider()),
      ],
    );
  }
}
