import 'package:flutter/material.dart';

/// FAN iD palette from the DS-01 design-system board.
///
/// The first seven values come directly from the design tokens. The neutral
/// colors that follow are derived shared tokens so screens do not invent their
/// own magic gray values.
///
/// No design-system color should be hard-coded outside this file.
///
/// Note de compatibilite : toutes les valeurs sont des constantes ARGB
/// explicites. On evite volontairement `withOpacity()` (deprecie a partir de
/// Flutter 3.27) et `withValues()` (indisponible avant 3.27), afin que le
/// prototype reste analysable proprement sur les deux versions.
abstract final class FanColors {
  // ---------------------------------------------------------------------
  // Values labeled in DS-01
  // ---------------------------------------------------------------------

  /// « Navy base » — fonds sombres, texte de titre.
  static const Color navy = Color(0xFF0E2A4D);

  /// « Primary » — liens, prix, fin du degrade de marque.
  static const Color primary = Color(0xFF1663C7);

  /// Cyan accent: focus, ticket accent bar, and scanner frame.
  static const Color cyan = Color(0xFF22D3EE);

  /// Teal: charts, event artwork, and live badges.
  static const Color teal = Color(0xFF0EA5B7);

  /// « Succes ».
  static const Color success = Color(0xFF16B981);

  /// « Danger ».
  static const Color danger = Color(0xFFEF4444);

  /// « Alerte ».
  static const Color warning = Color(0xFFF59E0B);

  // ---------------------------------------------------------------------
  // Neutral colors derived from the design
  // ---------------------------------------------------------------------

  /// General background for light screens.
  static const Color background = Color(0xFFF4F7FB);

  /// Surface for cards, inputs, and sheets.
  static const Color surface = Color(0xFFFFFFFF);

  /// Surface creusee : onglet inactif, carte desactivee.
  static const Color surfaceSunken = Color(0xFFF1F5FB);

  /// Border color for inputs and cards.
  static const Color border = Color(0xFFDCE4EF);

  /// Texte principal (identique a [navy], nomme separement par intention).
  static const Color textPrimary = navy;

  /// Texte secondaire : sous-titres, metadonnees.
  static const Color textSecondary = Color(0xFF64748B);

  /// Placeholder et texte desactive.
  static const Color textPlaceholder = Color(0xFF94A3B8);

  /// Disabled-button background.
  static const Color disabled = Color(0xFFCBD5E1);

  /// Secondary text on a navy background.
  static const Color onNavySecondary = Color(0xFFA8C0DC);

  /// Navy shades used in dark gradients.
  static const Color navyDeep = Color(0xFF0B2140);
  static const Color navySoft = Color(0xFF123A66);

  /// Translucent surface placed on a navy background.
  /// bandeau d information du QR).
  static const Color onNavySurface = Color(0x1FFFFFFF);
  static const Color onNavyBorder = Color(0x33FFFFFF);

  /// Translucent surface placed on a solid-color background.
  /// Used by the white disks on scanner result screens.
  static const Color onColorSurface = Color(0x26FFFFFF);

  /// Voile sombre : puce de motif du refus, superposition de tiroir.
  static const Color scrim = Color(0x33000000);

  /// Encre ambre du badge « En attente ». L ambre sature de [warning] est
  /// Darkened variant used where the original shade would lack contrast.
  /// contraste.
  static const Color warningInk = Color(0xFFB4740A);

  /// Very pale cyan used for decorative event artwork.
  static const Color cyanVeil = Color(0x2622D3EE);

  /// Halo cyan du champ en focus.
  static const Color cyanGlow = Color(0x3322D3EE);

  // ---------------------------------------------------------------------
  // Badge tints: light state-color backgrounds on white
  // ---------------------------------------------------------------------

  static const Color successTint = Color(0xFFDEF5ED);
  static const Color dangerTint = Color(0xFFFDE5E5);
  static const Color warningTint = Color(0xFFFEF1DD);
  static const Color cyanTint = Color(0xFFE0F9FD);
  static const Color tealTint = Color(0xFFDDF2F5);
  static const Color neutralTint = surfaceSunken;

  // ---------------------------------------------------------------------
  // Degrades
  // ---------------------------------------------------------------------

  /// « Degrade marque · cyan -> bleu ». Bouton primaire, avatar, barre KPI.
  static const LinearGradient brandGradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: <Color>[cyan, primary],
  );

  /// Dark background for immersive screens such as splash, QR, scanner, and hero.
  static const LinearGradient navyGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[navyDeep, navySoft],
  );

  /// Fond de l ecran « Acces valide » (SCN-04).
  static const LinearGradient successGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0xFF13A574), Color(0xFF0E8F63)],
  );

  /// Fond de l ecran « Acces refuse » (SCN-05).
  static const LinearGradient dangerGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0xFFE94A4A), Color(0xFFCE2F2F)],
  );
}
