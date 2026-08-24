import 'package:flutter/material.dart';

import '../colors.dart';
import '../radius.dart';
import '../spacing.dart';
import '../typography.dart';

/// Les six badges de statut de DS-01.
///
/// L enumeration est FERMEE : elle reprend exactement les libelles de la
/// planche. Un statut absent d ici signale un manque de la maquette, pas une
/// occasion d inventer une septieme couleur.
enum FanBadgeStatus {
  /// « Valide » — vert, avec pastille.
  valide(FanColors.successTint, FanColors.success, 'Valide', dot: true),

  /// « Utilise » — neutre.
  utilise(FanColors.neutralTint, FanColors.textSecondary, 'Utilisé'),

  /// « Transfere » — cyan pale, texte navy.
  transfere(FanColors.cyanTint, FanColors.navy, 'Transféré'),

  /// « En attente » — ambre.
  enAttente(FanColors.warningTint, FanColors.warningInk, 'En attente'),

  /// « EN DIRECT » — cyan, avec pastille.
  enDirect(FanColors.cyanTint, FanColors.teal, 'EN DIRECT', dot: true),

  /// « Epuise » — rouge pale.
  epuise(FanColors.dangerTint, FanColors.danger, 'Épuisé');

  const FanBadgeStatus(
    this.background,
    this.foreground,
    this.defaultLabel, {
    this.dot = false,
  });

  final Color background;
  final Color foreground;
  final String defaultLabel;
  final bool dot;
}

/// Badge de statut. `label` permet de reutiliser une variante avec un autre
/// texte (« J-3 », « Vente ouverte », « Billets bientot epuises »), sans
/// creer de nouvelle couleur.
class FanIdBadge extends StatelessWidget {
  const FanIdBadge({
    required this.status,
    this.label,
    this.onDark = false,
    super.key,
  });

  final FanBadgeStatus status;
  final String? label;

  /// Variante posee sur un fond navy : le fond du badge devient translucide.
  final bool onDark;

  @override
  Widget build(BuildContext context) {
    final String text = label ?? status.defaultLabel;
    final Color fg = onDark ? FanColors.cyan : status.foreground;

    return Semantics(
      label: 'Statut : $text',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: FanSpacing.md,
          vertical: 6,
        ),
        decoration: BoxDecoration(
          color: onDark ? FanColors.onNavySurface : status.background,
          borderRadius: FanRadius.brFull,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            if (status.dot) ...<Widget>[
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: fg,
                  borderRadius: FanRadius.brFull,
                ),
              ),
              const SizedBox(width: 6),
            ],
            Flexible(
              child: Text(
                text,
                overflow: TextOverflow.ellipsis,
                style: FanType.caption.copyWith(
                  color: fg,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
