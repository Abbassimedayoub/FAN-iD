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
/// Configure aussi les composants Material utilises par les parcours metier.
/// Ne modifie pas l'echelle typographique de l'utilisateur.
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
      onSurface: FanColors.navy,
      onSurfaceVariant: FanColors.textSecondary,
      outlineVariant: FanColors.border,
      surfaceContainerLow: FanColors.surface,
      surfaceContainerHighest: FanColors.surfaceSunken,
      tertiaryContainer: const Color(0xFFF9F5FE),
      onTertiaryContainer: const Color(0xFF6B21A8),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: FanType.bodyFamily,
      textTheme: const TextTheme(
        headlineSmall: FanType.h1,
        headlineMedium: FanType.h1,
        titleLarge: FanType.h2,
        titleMedium: FanType.h3,
        titleSmall: FanType.bodyStrong,
        bodyLarge: FanType.body,
        bodyMedium: FanType.body,
        bodySmall: FanType.caption,
        labelLarge: FanType.label,
        labelMedium: FanType.label,
        labelSmall: FanType.caption,
      ),
      cardTheme: CardThemeData(
        color: FanColors.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: FanColors.border),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          backgroundColor: FanColors.primary,
          foregroundColor: Colors.white,
          textStyle: FanType.button.copyWith(fontSize: 15),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 48),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          foregroundColor: FanColors.primary,
          backgroundColor: Colors.white,
          side: const BorderSide(color: FanColors.primary),
          textStyle: FanType.button.copyWith(fontSize: 15),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.all(16),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: FanColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: FanColors.primary, width: 2),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: Colors.white,
        selectedColor: const Color(0xFFDCE9FA),
        side: const BorderSide(color: FanColors.border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        labelStyle: FanType.label,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      ),
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        iconColor: FanColors.primary,
        titleTextStyle: FanType.bodyStrong,
        subtitleTextStyle: FanType.caption,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
      ),
      scaffoldBackgroundColor: FanColors.background,
      splashFactory: InkRipple.splashFactory,
      // Cible tactile minimale posee au niveau du theme, pour ne pas dependre
      // de la vigilance de chaque ecran.
      materialTapTargetSize: MaterialTapTargetSize.padded,
      appBarTheme: const AppBarTheme(
        backgroundColor: FanColors.surface,
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
