import 'package:flutter/material.dart';

/// Palette FAN iD — issue de la planche `DS-01 · Design System`.
///
/// Les sept premieres valeurs sont LUES LITTERALEMENT sur la maquette : chaque
/// pastille de DS-01 y porte son hexadecimal. Les neutres qui suivent sont
/// derives du rendu ; la planche ne les nomme pas, mais sans eux chaque ecran
/// reinventerait son propre gris — exactement la « valeur magique » que ce
/// prototype doit interdire.
///
/// Aucune couleur ne doit etre ecrite en dur ailleurs que dans ce fichier.
///
/// Note de compatibilite : toutes les valeurs sont des constantes ARGB
/// explicites. On evite volontairement `withOpacity()` (deprecie a partir de
/// Flutter 3.27) et `withValues()` (indisponible avant 3.27), afin que le
/// prototype reste analysable proprement sur les deux versions.
abstract final class FanColors {
  // ---------------------------------------------------------------------
  // Valeurs libellees dans DS-01
  // ---------------------------------------------------------------------

  /// « Navy base » — fonds sombres, texte de titre.
  static const Color navy = Color(0xFF0E2A4D);

  /// « Primary » — liens, prix, fin du degrade de marque.
  static const Color primary = Color(0xFF1663C7);

  /// « Cyan accent » — focus, barre d accent des billets, cadre du scanner.
  static const Color cyan = Color(0xFF22D3EE);

  /// « Teal » — courbes, vignettes d evenement, badge EN DIRECT.
  static const Color teal = Color(0xFF0EA5B7);

  /// « Succes ».
  static const Color success = Color(0xFF16B981);

  /// « Danger ».
  static const Color danger = Color(0xFFEF4444);

  /// « Alerte ».
  static const Color warning = Color(0xFFF59E0B);

  // ---------------------------------------------------------------------
  // Neutres — derives du rendu, non libelles dans DS-01
  // ---------------------------------------------------------------------

  /// Fond general des ecrans clairs.
  static const Color background = Color(0xFFE9EFF8);

  /// Surface des cartes, champs et feuilles.
  static const Color surface = Color(0xFFFFFFFF);

  /// Surface creusee : onglet inactif, carte desactivee.
  static const Color surfaceSunken = Color(0xFFF1F5FB);

  /// Contour des champs et des cartes.
  static const Color border = Color(0xFFDCE4EF);

  /// Texte principal (identique a [navy], nomme separement par intention).
  static const Color textPrimary = navy;

  /// Texte secondaire : sous-titres, metadonnees.
  static const Color textSecondary = Color(0xFF64748B);

  /// Placeholder et texte desactive.
  static const Color textPlaceholder = Color(0xFF94A3B8);

  /// Fond du bouton desactive (« Epuise » dans DS-01).
  static const Color disabled = Color(0xFFCBD5E1);

  /// Texte secondaire pose sur un fond navy.
  static const Color onNavySecondary = Color(0xFFA8C0DC);

  /// Nuances de navy composant les fonds degrades sombres.
  static const Color navyDeep = Color(0xFF0B2140);
  static const Color navySoft = Color(0xFF123A66);

  /// Surface translucide posee sur un fond navy (boutons ronds du scanner,
  /// bandeau d information du QR).
  static const Color onNavySurface = Color(0x1FFFFFFF);
  static const Color onNavyBorder = Color(0x33FFFFFF);

  /// Surface translucide posee sur un aplat de couleur pleine — le disque
  /// blanc des ecrans SCN-04 et SCN-05.
  static const Color onColorSurface = Color(0x26FFFFFF);

  /// Voile sombre : puce de motif du refus, superposition de tiroir.
  static const Color scrim = Color(0x33000000);

  /// Encre ambre du badge « En attente ». L ambre sature de [warning] est
  /// illisible sur sa propre teinte pale ; cette version assombrie tient le
  /// contraste.
  static const Color warningInk = Color(0xFFB4740A);

  /// Cyan tres dilue : motif decoratif des visuels d evenement.
  static const Color cyanVeil = Color(0x2622D3EE);

  /// Halo cyan du champ en focus.
  static const Color cyanGlow = Color(0x3322D3EE);

  // ---------------------------------------------------------------------
  // Teintes de badge — fond a ~14 % de la couleur d etat, sur blanc
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

  /// Fond sombre des ecrans immersifs (splash, QR, scanner, hero).
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
