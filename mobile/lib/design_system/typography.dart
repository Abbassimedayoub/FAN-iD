import 'package:flutter/material.dart';

import 'colors.dart';

/// FAN iD typography scale from the DS-01 design-system board.
///
/// « Titre H1 — Sora 28 » / « Titre H2 — Sora 22 » / « Titre H3 — Sora 18 »
/// « Corps de texte — Inter 15 » / « Legende — Inter 12 ».
///
/// ## No runtime font downloads
///
/// This file does not use `google_fonts`. Both families are resolved from fonts
/// bundled with the application.
///
/// 1. offline first launch still uses the intended brand fonts;
/// 2. startup makes no unnecessary third-party font request;
/// 3. rendering stays deterministic for layout tests.
///    aussi.
///
/// Styles are const so they can be reused in constant constructors.
abstract final class FanType {
  /// Family names as declared in `pubspec.yaml`.
  static const String headingFamily = 'Sora';
  static const String bodyFamily = 'Inter';

  static const TextStyle h1 = TextStyle(
    fontFamily: headingFamily,
    fontSize: 28,
    fontWeight: FontWeight.w700,
    height: 1.2,
    color: FanColors.textPrimary,
  );

  static const TextStyle h2 = TextStyle(
    fontFamily: headingFamily,
    fontSize: 22,
    fontWeight: FontWeight.w700,
    height: 1.25,
    color: FanColors.textPrimary,
  );

  static const TextStyle h3 = TextStyle(
    fontFamily: headingFamily,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    height: 1.3,
    color: FanColors.textPrimary,
  );

  static const TextStyle body = TextStyle(
    fontFamily: bodyFamily,
    fontSize: 15,
    fontWeight: FontWeight.w400,
    height: 1.45,
    color: FanColors.textPrimary,
  );

  static const TextStyle bodyStrong = TextStyle(
    fontFamily: bodyFamily,
    fontSize: 15,
    fontWeight: FontWeight.w600,
    height: 1.45,
    color: FanColors.textPrimary,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: bodyFamily,
    fontSize: 12,
    fontWeight: FontWeight.w400,
    height: 1.4,
    color: FanColors.textSecondary,
  );

  /// Libelle de champ, de badge ou d onglet.
  static const TextStyle label = TextStyle(
    fontFamily: bodyFamily,
    fontSize: 13,
    fontWeight: FontWeight.w600,
    height: 1.3,
    color: FanColors.textPrimary,
  );

  /// Texte de bouton.
  static const TextStyle button = TextStyle(
    fontFamily: bodyFamily,
    fontSize: 16,
    fontWeight: FontWeight.w700,
    height: 1.2,
  );

  /// Large numeric style for KPIs and countdowns.
  static const TextStyle display = TextStyle(
    fontFamily: headingFamily,
    fontSize: 32,
    fontWeight: FontWeight.w700,
    height: 1.1,
    color: FanColors.textPrimary,
  );

  /// Splash wordmark style: Sora with wide tracking.
  static const TextStyle wordmark = TextStyle(
    fontFamily: headingFamily,
    fontSize: 34,
    fontWeight: FontWeight.w700,
    letterSpacing: 6,
    height: 1.1,
  );
}
