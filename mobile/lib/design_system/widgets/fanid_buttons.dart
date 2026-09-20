import 'package:flutter/material.dart';

import '../colors.dart';
import '../radius.dart';
import '../shadows.dart';
import '../spacing.dart';
import '../typography.dart';

/// FAN iD button variants from the DS-01 design system.
///
/// Three rules apply to every variant and are enforced by the components themselves:
///
/// 1. **touch target >= 48 dp**, even when the drawn shape is smaller;
///    petite. Taille visuelle et zone tapable sont deux choses distinctes ;
///    visual size and hit target must remain separate concerns;
/// 2. **button semantics** with an accessible label;
///    d ecran et l etat `enabled` correctement propage ;
/// 3. **disabled state distinguished by background and text color**, never opacity alone.
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

  /// `null` disables the button; [loading] also forces the disabled state.
  final VoidCallback? onPressed;
  final bool expanded;

  /// Variante « Action compacte » de DS-01.
  final bool compact;

  /// Show progress inside the button and make it inert.
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
            // Use minHeight rather than height so large text can grow the button instead of overflowing.
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

  /// Variant intended for a navy background.
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
            // Even a link keeps a 48 dp touch target.
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
    // The visual chip is 40 dp high, while its tappable area remains 48 dp for accessibility.
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
                // Vertical padding plus label height produces the intended visual size;
                // with larger text the chip grows instead of clipping.
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
/// This navigation control is grouped here because it is a button; the portable
/// bundle does not include the full navigation bar.
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

  /// Label read by assistive technology and shown as a tooltip; icon-only buttons require an accessible name.
  final String tooltip;
  final bool onDark;

  /// Visual disk diameter; the touch target never drops below 48 dp regardless of this value.
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
