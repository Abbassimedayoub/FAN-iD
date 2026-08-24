import 'package:flutter/material.dart';

import 'colors.dart';

/// Typographie FAN iD — echelle litterale de la planche `DS-01`.
///
/// « Titre H1 — Sora 28 » / « Titre H2 — Sora 22 » / « Titre H3 — Sora 18 »
/// « Corps de texte — Inter 15 » / « Legende — Inter 12 ».
///
/// ## Aucun telechargement de police a l execution
///
/// Ce fichier n utilise PAS `google_fonts`. Les deux familles sont declarees
/// par leur nom et resolues depuis les polices embarquees dans l application
/// (cf. `PUBSPEC_CHANGES.md`). Trois raisons, dans cet ordre :
///
/// 1. un premier lancement hors ligne afficherait le splash — tout premier
///    ecran vu — dans une police systeme, pas dans celle de la marque ;
/// 2. une requete vers un tiers au demarrage pose une question RGPD que ce
///    projet n a aucune raison de se creer ;
/// 3. le rendu devient deterministe, donc les tests de mise en page le sont
///    aussi.
///
/// Les styles sont `const` : leur cout d instanciation est nul et ils peuvent
/// etre utilises dans des constructeurs constants.
abstract final class FanType {
  /// Nom des familles tel que declare dans `pubspec.yaml`.
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

  /// Grand chiffre : KPI, compte a rebours (non libelle dans DS-01).
  static const TextStyle display = TextStyle(
    fontFamily: headingFamily,
    fontSize: 32,
    fontWeight: FontWeight.w700,
    height: 1.1,
    color: FanColors.textPrimary,
  );

  /// Le mot-symbole « FANID » du splash : Sora, tres espace.
  static const TextStyle wordmark = TextStyle(
    fontFamily: headingFamily,
    fontSize: 34,
    fontWeight: FontWeight.w700,
    letterSpacing: 6,
    height: 1.1,
  );
}
