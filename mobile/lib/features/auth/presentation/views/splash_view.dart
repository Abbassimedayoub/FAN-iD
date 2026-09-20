import 'package:flutter/material.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

/// FAN-01 · Splash — **vue purement visuelle**.
///
/// ## What this view does not do
///
/// * no `Timer`, `initState`, or `Future`;
/// * no `context.go` and no `go_router` import;
/// * no authentication-state lookup.
///
/// It **renders**; it does not **decide** navigation.
/// vers Login, aller vers l accueil — appartient au `redirect` du routeur, qui
/// observe deja `authControllerProvider`. Deux autorites de navigation
/// concurrentes (un `Timer` local et un `redirect`) finissent toujours par se
/// Keeping those responsibilities separate avoids timing-dependent navigation bugs.
///
/// ## Expected integration
///
/// ```dart
/// GoRoute(
///   path: '/',
///   builder: (_, __) => const SplashView(),
/// )
/// ```
/// Route from the global redirect according to authentication state.
/// `ref.watch(authControllerProvider)` :
/// `AsyncLoading` stays on `/`; `AsyncData(null)` goes to `/login`.
/// `AsyncData(session)` => l accueil.
///
/// The view accepts an optional [statusLabel] for assistive-technology announcements; the caller supplies the actual state.
class SplashView extends StatelessWidget {
  const SplashView({
    this.statusLabel = 'Vérification de votre session…',
    this.versionLabel = 'v1.0.0',
    super.key,
  });

  /// Texte annonce par [LoadingView] (region vivante). Purement descriptif.
  final String statusLabel;

  /// Displayed in the footer; the caller injects the real version.
  final String versionLabel;

  static const String tagline = 'Votre billet. Votre identité. Zéro fraude.';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: NavyBackdrop(
        child: SafeArea(
          // Use scrolling rather than Spacer so large text scales without overflow.
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
