import 'package:flutter/material.dart';

import 'colors.dart';
import 'typography.dart';

/// Theme global FAN iD.
///
/// Il ne fait qu une chose : injecter les tokens dans Material pour que les
/// widgets natifs (curseur de champ, ripple, selection de texte) restent
/// coherents avec la maquette. Les composants FAN iD, eux, lisent les tokens
/// directement — le theme n est pas leur source de verite.
///
/// Ce fichier ne configure DELIBEREMENT pas :
/// * `cardTheme` — son type a change entre Flutter 3.24 (`CardTheme`) et 3.27
///   (`CardThemeData`) ; aucun `Card` Material n est utilise ici ;
/// * l echelle typographique de l utilisateur — voir la note d accessibilite
///   plus bas.
///
/// ## Accessibilite : aucun plafond sur l echelle de texte
///
/// Une version anterieure de ce theme bornait `textScaler` a 1.3. C etait un
/// defaut : le critere WCAG 2.1 §1.4.4 demande 200 % de redimensionnement, et
/// un plafond a 1.3 ecrase silencieusement le reglage systeme d un
/// utilisateur malvoyant. La bonne parade n est pas de contraindre
/// l utilisateur mais de rendre les ecrans defilants — ce que font
/// `SplashView` et `LoginView`.
abstract final class FanTheme {
  static ThemeData get light {
    final ColorScheme scheme = ColorScheme.fromSeed(
      seedColor: FanColors.primary,
      brightness: Brightness.light,
    ).copyWith(
      primary: FanColors.primary,
      secondary: FanColors.cyan,
      error: FanColors.danger,
      surface: FanColors.surface,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: FanType.bodyFamily,
      scaffoldBackgroundColor: FanColors.background,
      splashFactory: InkRipple.splashFactory,
      // Cible tactile minimale posee au niveau du theme, pour ne pas dependre
      // de la vigilance de chaque ecran.
      materialTapTargetSize: MaterialTapTargetSize.padded,
      appBarTheme: const AppBarTheme(
        backgroundColor: FanColors.background,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: FanType.h3,
        iconTheme: IconThemeData(color: FanColors.textPrimary),
      ),
      dividerTheme: const DividerThemeData(
        color: FanColors.border,
        thickness: 1,
        space: 1,
      ),
    );
  }
}
