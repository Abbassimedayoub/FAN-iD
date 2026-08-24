import 'package:flutter/material.dart';

/// Deux niveaux d ombre, et deux seulement.
///
/// DS-01 ne montre rien d autre : une ombre diffuse sous les cartes blanches,
/// et un halo colore sous le bouton primaire. En ajouter un troisieme serait
/// deja un redesign.
abstract final class FanShadows {
  /// Ombre douce des cartes.
  static const List<BoxShadow> card = <BoxShadow>[
    BoxShadow(
      color: Color(0x140E2A4D),
      blurRadius: 18,
      offset: Offset(0, 6),
    ),
  ];

  /// Ombre des elements flottants (barre de navigation, feuille basse).
  static const List<BoxShadow> raised = <BoxShadow>[
    BoxShadow(
      color: Color(0x1F0E2A4D),
      blurRadius: 26,
      offset: Offset(0, -4),
    ),
  ];

  /// Halo colore du bouton primaire (bleu marque a ~34 %).
  static const List<BoxShadow> brand = <BoxShadow>[
    BoxShadow(
      color: Color(0x571663C7),
      blurRadius: 20,
      offset: Offset(0, 8),
    ),
  ];
}
