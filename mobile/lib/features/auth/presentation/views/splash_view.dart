import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

/// FAN-01 · Splash — **vue purement visuelle**.
///
/// ## Ce que cette vue ne fait pas, et ne doit jamais faire
///
/// * aucun `Timer`, aucun `initState`, aucun `Future` ;
/// * aucun `context.go`, aucun import `go_router` ;
/// * aucune lecture de l etat d authentification.
///
/// Elle **affiche**, elle ne **decide** pas. La decision — rester ici, aller
/// vers Login, aller vers l accueil — appartient au `redirect` du routeur, qui
/// observe deja `authControllerProvider`. Deux autorites de navigation
/// concurrentes (un `Timer` local et un `redirect`) finissent toujours par se
/// contredire, et le bug qui en resulte n apparait que sur un reseau lent.
///
/// ## Integration attendue dans le vrai depot
///
/// ```dart
/// GoRoute(
///   path: '/',
///   builder: (_, __) => const SplashView(),
/// )
/// ```
/// puis, dans le `redirect` global, router selon
/// `ref.watch(authControllerProvider)` :
/// `AsyncLoading` => rester sur `/` ; `AsyncData(null)` => `/login` ;
/// `AsyncData(session)` => l accueil.
///
/// La vue accepte un [statusLabel] optionnel pour annoncer au lecteur d ecran
/// ce qui se passe. Elle ne le devine pas : c est l appelant qui le sait.
class SplashView extends StatelessWidget {
  const SplashView({
    this.statusLabel = 'Vérification de votre session…',
    this.versionLabel = 'v1.0.0',
    super.key,
  });

  /// Texte annonce par [LoadingView] (region vivante). Purement descriptif.
  final String statusLabel;

  /// Affiche en pied d ecran. L appelant y injecte la version reelle.
  final String versionLabel;

  static const String tagline = 'Votre billet. Votre identité. Zéro fraude.';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: NavyBackdrop(
        child: SafeArea(
          // Defilement plutot que `Spacer` : a une echelle de texte de 2.0, la
          // baseline et le mot-symbole doublent de hauteur. Un `Column` rigide
          // produirait la bande jaune et noire de Flutter ; ici l ecran
          // defile, et reste centre tant qu il tient.
          child: LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              return SingleChildScrollView(
                padding: const EdgeInsets.symmetric(
                  horizontal: FanSpacing.screenH,
                  vertical: FanSpacing.xxl,
                ),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight > FanSpacing.xxl * 2
                        ? constraints.maxHeight - FanSpacing.xxl * 2
                        : 0.0,
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      const FanIdLogo(size: 116),
                      const SizedBox(height: FanSpacing.xxl),
                      const FanIdWordmark(),
                      const SizedBox(height: FanSpacing.md),
                      Text(
                        tagline,
                        textAlign: TextAlign.center,
                        style: FanType.body.copyWith(
                          color: FanColors.onNavySecondary,
                        ),
                      ),
                      const SizedBox(height: FanSpacing.xxxl),
                      LoadingView(onDark: true, message: statusLabel),
                      const SizedBox(height: FanSpacing.xxxl),
                      Text(
                        versionLabel,
                        textAlign: TextAlign.center,
                        style: FanType.caption.copyWith(
                          color: FanColors.onNavySecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
