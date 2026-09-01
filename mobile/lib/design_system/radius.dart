import 'package:flutter/widgets.dart';

/// Rayons FAN iD, estimes sur le rendu de DS-01.
abstract final class FanRadius {
  /// Chips de filtre, petites vignettes.
  static const double sm = 8;

  /// Champs, boutons, cases OTP.
  static const double md = 12;

  /// Cartes billet, cartes evenement, tuiles KPI.
  static const double lg = 16;

  /// Carte « A la une », feuille basse, carte de connexion web.
  static const double xl = 22;

  /// Badges, avatars, boutons ronds du scanner.
  static const double full = 999;

  static const BorderRadius brSm = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius brMd = BorderRadius.all(Radius.circular(md));
  static const BorderRadius brLg = BorderRadius.all(Radius.circular(lg));
  static const BorderRadius brXl = BorderRadius.all(Radius.circular(xl));
  static const BorderRadius brFull = BorderRadius.all(Radius.circular(full));
}
