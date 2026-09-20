import 'package:flutter/material.dart';

import 'colors.dart';
import 'typography.dart';

/// Global FAN iD theme.
///
/// Its role is to inject design tokens into Material so native widgets such as
/// cursors, ripples, and text selection stay consistent with the product UI.
/// FAN iD components read tokens directly; the theme is not their source of
/// truth.
///
/// It also configures Material components used by business flows and never
/// overrides the user's typography scale.
///
/// Accessibility: there is no cap on text scaling. Earlier code capped
/// `textScaler` at 1.3, which silently overrode the system preference. The
/// correct response is to make screens scrollable rather than constrain users.
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
      // Set the minimum touch target at theme level instead of relying on each
      // screen to remember it.
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
