/// Echelle d espacement FAN iD : 4 / 8 / 12 / 16 / 20 / 24 / 32.
///
/// Toute marge ou tout ecart doit provenir de cette echelle. Une valeur hors
/// echelle dans un ecran est un defaut, pas un ajustement.
abstract final class FanSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;

  /// Marge laterale standard d un ecran mobile (mesuree sur la maquette).
  static const double screenH = xl;

  /// Hauteur minimale d une cible tactile — contrainte d accessibilite
  /// rappelee dans le cahier des charges : >= 48 dp.
  static const double minTouchTarget = 48;
}
