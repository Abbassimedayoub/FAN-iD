import 'package:flutter/material.dart';

import '../colors.dart';
import '../radius.dart';
import '../shadows.dart';
import '../spacing.dart';
import '../typography.dart';

/// Boutons FAN iD — les variantes de la planche `DS-01`.
///
/// Trois regles s appliquent a toutes, et sont tenues par les composants
/// eux-memes, jamais par l appelant :
///
/// 1. **cible tactile >= 48 dp**, meme quand la forme dessinee est plus
///    petite. Taille visuelle et zone tapable sont deux choses distinctes ;
///    les confondre est precisement le defaut qui avait fait naitre
///    [FanIdFilterChip] a 40 dp dans une version anterieure ;
/// 2. **`Semantics` de type bouton**, avec le libelle lu par le lecteur
///    d ecran et l etat `enabled` correctement propage ;
/// 3. **etat desactive distingue par le fond ET par la couleur du texte**,
///    jamais par la seule opacite.
class FanIdPrimaryButton extends StatelessWidget {
  const FanIdPrimaryButton({
    required this.label,
    required this.onPressed,
    this.expanded = true,
    this.compact = false,
    this.loading = false,
    this.icon,
    super.key,
  });

  final String label;

  /// `null` => bouton desactive. [loading] force egalement la desactivation.
  final VoidCallback? onPressed;
  final bool expanded;

  /// Variante « Action compacte » de DS-01.
  final bool compact;

  /// Affiche un indicateur de progression DANS le bouton et le rend inerte.
  ///
  /// On garde volontairement le bouton en place au lieu de le remplacer par un
  /// spinner : la mise en page ne saute pas, et le lecteur d ecran continue
  /// d annoncer un bouton — desactive — plutot que de voir disparaitre
  /// l element qui avait le focus.
  final bool loading;

  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final bool enabled = onPressed != null && !loading;
    final Color foreground =
        enabled || loading ? Colors.white : FanColors.textPlaceholder;
    final double minHeight =
        compact ? FanSpacing.minTouchTarget : FanSpacing.minTouchTarget + 8;

    final Widget content = Row(
      mainAxisSize: expanded ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        if (loading) ...<Widget>[
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(
              strokeWidth: 2.4,
              valueColor: AlwaysStoppedAnimation<Color>(foreground),
            ),
          ),
          const SizedBox(width: FanSpacing.md),
        ] else if (icon != null) ...<Widget>[
          Icon(icon, size: 18, color: foreground),
          const SizedBox(width: FanSpacing.sm),
        ],
        Flexible(
          child: Text(
            label,
            textAlign: TextAlign.center,
            overflow: TextOverflow.ellipsis,
            style: FanType.button.copyWith(color: foreground),
          ),
        ),
      ],
    );

    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: enabled ? onPressed : null,
          borderRadius: FanRadius.brMd,
          child: Ink(
            width: expanded ? double.infinity : null,
            padding: EdgeInsets.symmetric(
              horizontal: compact ? FanSpacing.lg : FanSpacing.xxl,
              vertical: FanSpacing.md,
            ),
            decoration: BoxDecoration(
              gradient: enabled || loading ? FanColors.brandGradient : null,
              color: enabled || loading ? null : FanColors.disabled,
              borderRadius: FanRadius.brMd,
              boxShadow: enabled ? FanShadows.brand : null,
            ),
            // `minHeight` plutot que `height` : a echelle de texte 2.0 le
            // libelle doit pouvoir faire grandir le bouton au lieu de deborder.
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: minHeight),
              child: Center(child: content),
            ),
          ),
        ),
      ),
    );
  }
}

/// Bouton secondaire : fond blanc, contour bleu, texte bleu.
class FanIdSecondaryButton extends StatelessWidget {
  const FanIdSecondaryButton({
    required this.label,
    required this.onPressed,
    this.expanded = true,
    this.onDark = false,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool expanded;

  /// Variante posee sur un fond navy.
  final bool onDark;

  @override
  Widget build(BuildContext context) {
    final bool enabled = onPressed != null;
    final Color accent = onDark ? FanColors.cyan : FanColors.primary;

    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: FanRadius.brMd,
          child: Ink(
            width: expanded ? double.infinity : null,
            padding: const EdgeInsets.symmetric(
              horizontal: FanSpacing.xxl,
              vertical: FanSpacing.md,
            ),
            decoration: BoxDecoration(
              color: onDark ? Colors.transparent : FanColors.surface,
              borderRadius: FanRadius.brMd,
              border: Border.all(
                color: enabled ? accent : FanColors.border,
                width: 1.6,
              ),
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                minHeight: FanSpacing.minTouchTarget + 8,
              ),
              child: Center(
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  overflow: TextOverflow.ellipsis,
                  style: FanType.button.copyWith(
                    color: enabled ? accent : FanColors.textPlaceholder,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Bouton destructif : rouge plein.
class FanIdDangerButton extends StatelessWidget {
  const FanIdDangerButton({
    required this.label,
    required this.onPressed,
    this.expanded = true,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool expanded;

  @override
  Widget build(BuildContext context) {
    final bool enabled = onPressed != null;

    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: FanRadius.brMd,
          child: Ink(
            width: expanded ? double.infinity : null,
            padding: const EdgeInsets.symmetric(
              horizontal: FanSpacing.xxl,
              vertical: FanSpacing.md,
            ),
            decoration: BoxDecoration(
              color: enabled ? FanColors.danger : FanColors.disabled,
              borderRadius: FanRadius.brMd,
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                minHeight: FanSpacing.minTouchTarget + 8,
              ),
              child: Center(
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  overflow: TextOverflow.ellipsis,
                  style: FanType.button.copyWith(
                    color: enabled ? Colors.white : FanColors.textPlaceholder,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Bouton texte / lien (« Mot de passe oublie ? »).
class FanIdLinkButton extends StatelessWidget {
  const FanIdLinkButton({
    required this.label,
    required this.onPressed,
    this.color,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final bool enabled = onPressed != null;

    return Semantics(
      button: true,
      link: true,
      enabled: enabled,
      label: label,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: FanRadius.brSm,
          child: ConstrainedBox(
            // Meme un lien reste une cible tactile de 48 dp de haut.
            constraints: const BoxConstraints(
              minHeight: FanSpacing.minTouchTarget,
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: FanSpacing.sm),
              child: Align(
                alignment: Alignment.center,
                widthFactor: 1,
                child: Text(
                  label,
                  style: FanType.bodyStrong.copyWith(
                    color: enabled
                        ? (color ?? FanColors.primary)
                        : FanColors.textPlaceholder,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Chip de filtre (« Football », « Ce week-end », ...).
class FanIdFilterChip extends StatelessWidget {
  const FanIdFilterChip({
    required this.label,
    required this.selected,
    required this.onPressed,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    // La pastille MESURE 40 dp de haut — c est ce que montre la maquette —
    // mais la ZONE TAPABLE en fait 48. C est la correction du defaut
    // d accessibilite de la version precedente, ou le chip entier tombait a
    // 40 dp.
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: FanRadius.brFull,
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              minHeight: FanSpacing.minTouchTarget,
            ),
            child: Center(
              child: Ink(
                // 10 dp de padding vertical + la hauteur du libelle donnent
                // les ~40 dp dessines sur la maquette. A echelle de texte
                // elevee, la pastille grandit avec son texte au lieu de le
                // rogner.
                padding: const EdgeInsets.symmetric(
                  horizontal: FanSpacing.lg,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: selected ? FanColors.navy : FanColors.surface,
                  borderRadius: FanRadius.brFull,
                  border: Border.all(
                    color: selected ? FanColors.navy : FanColors.border,
                  ),
                ),
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  style: FanType.label.copyWith(
                    color: selected ? Colors.white : FanColors.textPrimary,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Bouton rond (retour, fermeture, torche).
///
/// Provient de `fanid_navigation.dart` dans le prototype d origine. Il est
/// regroupe ici parce que c est un BOUTON, et parce que le bundle portable ne
/// reprend pas la barre de navigation — celle-ci depend d ecrans hors
/// Sprint 1.
class FanIdCircleButton extends StatelessWidget {
  const FanIdCircleButton({
    required this.icon,
    required this.onPressed,
    required this.tooltip,
    this.onDark = true,
    this.size = FanSpacing.minTouchTarget,
    super.key,
  });

  final IconData icon;
  final VoidCallback? onPressed;

  /// Libelle lu par le lecteur d ecran et affiche en infobulle. Obligatoire :
  /// un bouton sans texte visible doit toujours porter un nom accessible.
  final String tooltip;
  final bool onDark;

  /// Diametre DESSINE du disque. La cible tactile ne descend jamais sous
  /// 48 dp, quelle que soit cette valeur — c est la contrainte exterieure qui
  /// l impose, pas ce parametre.
  final double size;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      enabled: onPressed != null,
      label: tooltip,
      child: Tooltip(
        message: tooltip,
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            minWidth: FanSpacing.minTouchTarget,
            minHeight: FanSpacing.minTouchTarget,
          ),
          child: Center(
            child: Material(
              color: onDark ? FanColors.onNavySurface : FanColors.surface,
              shape: const CircleBorder(),
              child: InkWell(
                onTap: onPressed,
                customBorder: const CircleBorder(),
                child: SizedBox(
                  width: size,
                  height: size,
                  child: Icon(
                    icon,
                    size: 20,
                    color: onDark ? Colors.white : FanColors.textPrimary,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
