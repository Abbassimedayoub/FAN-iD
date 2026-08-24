import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

/// FAN-04 · Connexion — **vue visuelle pilotee de l exterieur**.
///
/// ## Contrat
///
/// Cette vue ne possede aucun etat metier. Elle recoit tout ce qu elle
/// affiche et remonte tout ce que l utilisateur declenche :
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
/// Elle n importe ni Riverpod, ni `go_router`, ni aucun controleur. Elle est
/// donc testable sans `ProviderScope` et sans routeur — ce qui compte quand la
/// couverture est protegee par une porte de non-regression stricte.
///
/// ## Trois invariants tenus par la vue
///
/// 1. **Le bouton est reellement inerte pendant [isLoading]** : `onPressed`
///    vaut `null`, ce n est pas un simple changement de couleur.
/// 2. **La validation clavier respecte [isLoading]** : `onSubmitted` est mis a
///    `null` sur le champ mot de passe. Griser le bouton sans neutraliser la
///    touche Entree laisse passer une double soumission — c est le piege
///    classique de cet ecran.
/// 3. **Aucun code machine ne peut s afficher** : [errorText] est un message
///    deja traduit. La correspondance `BusinessFailure.code` -> message
///    appartient a l appelant, pas a la vue. Voir `PORTING_MANIFEST.md`.
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

  /// Declenche la soumission. La vue ne sait pas ce que cela fait.
  final VoidCallback onSubmit;

  /// Soumission en cours : bouton inerte + indicateur, touche Entree
  /// neutralisee.
  final bool isLoading;

  /// Message d erreur DEJA TRADUIT, affiche sous le champ mot de passe.
  final String? errorText;

  /// Bandeau d information en haut du formulaire — par exemple
  /// [sessionExpiredNotice] apres un echec de rafraichissement.
  ///
  /// Il ne remplace pas l avertissement permanent de liaison d appareil, qui
  /// fait partie de la maquette et reste affiche en bas.
  final String? noticeText;

  final VoidCallback? onForgotPassword;
  final VoidCallback? onRegister;

  /// Message a passer dans [noticeText] apres une expiration de session.
  static const String sessionExpiredNotice =
      'Votre session a expiré. Reconnectez-vous pour accéder à vos billets.';

  /// Avertissement permanent de la maquette FAN-04.
  static const String deviceBindingNotice =
      'Votre compte est lié à un seul appareil pour protéger vos billets '
      'contre la fraude.';

  @override
  Widget build(BuildContext context) {
    // Une seule source de verite pour « peut-on soumettre ? ». Le bouton et la
    // touche Entree la lisent tous les deux, donc ils ne peuvent pas diverger.
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
                      // `null` pendant le chargement : la touche Entree est
                      // reellement neutralisee, pas seulement le bouton.
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
