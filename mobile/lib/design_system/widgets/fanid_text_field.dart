import 'package:flutter/material.dart';

import '../colors.dart';
import '../radius.dart';
import '../spacing.dart';
import '../typography.dart';

/// Champ de saisie FAN iD — les trois etats de `DS-01` : defaut, focus,
/// erreur.
///
/// L erreur n est JAMAIS portee par la seule couleur : elle ajoute un message
/// texte sous le champ, une icone, et une region vivante annoncee au lecteur
/// d ecran. C est la regle « erreurs visibles autrement que par la couleur »
/// du cahier des charges.
///
/// Le composant ne connait aucune regle metier : `errorText` lui est fourni de
/// l exterieur, deja traduit en francais. Il ne doit jamais recevoir un code
/// machine.
class FanIdTextField extends StatefulWidget {
  const FanIdTextField({
    required this.label,
    this.controller,
    this.hintText,
    this.errorText,
    this.obscure = false,
    this.enabled = true,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.onChanged,
    this.onSubmitted,
    super.key,
  });

  final String label;
  final TextEditingController? controller;
  final String? hintText;

  /// Non nul => le champ passe en etat erreur.
  final String? errorText;

  /// Mot de passe : ajoute l action « Afficher » de la maquette.
  final bool obscure;

  final bool enabled;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final ValueChanged<String>? onChanged;

  /// Validation au clavier (touche Entree / « Go »).
  ///
  /// Passer `null` neutralise reellement la touche — c est ainsi qu un ecran
  /// en cours de soumission empeche une seconde validation, et pas seulement
  /// en grisant son bouton.
  final ValueChanged<String>? onSubmitted;

  @override
  State<FanIdTextField> createState() => _FanIdTextFieldState();
}

class _FanIdTextFieldState extends State<FanIdTextField> {
  late final FocusNode _focusNode = FocusNode()..addListener(_onFocusChanged);
  bool _focused = false;
  bool _revealed = false;

  void _onFocusChanged() {
    if (!mounted) {
      return;
    }
    setState(() => _focused = _focusNode.hasFocus);
  }

  @override
  void dispose() {
    _focusNode
      ..removeListener(_onFocusChanged)
      ..dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool hasError = widget.errorText != null;
    final Color borderColor = hasError
        ? FanColors.danger
        : _focused
            ? FanColors.cyan
            : FanColors.border;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(widget.label, style: FanType.label),
        const SizedBox(height: FanSpacing.sm),
        DecoratedBox(
          decoration: BoxDecoration(
            color: widget.enabled ? FanColors.surface : FanColors.surfaceSunken,
            borderRadius: FanRadius.brMd,
            border: Border.all(color: borderColor, width: _focused ? 2 : 1.2),
            boxShadow: _focused && !hasError
                ? const <BoxShadow>[
                    BoxShadow(color: FanColors.cyanGlow, blurRadius: 10),
                  ]
                : null,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              Expanded(
                child: TextField(
                  controller: widget.controller,
                  focusNode: _focusNode,
                  enabled: widget.enabled,
                  obscureText: widget.obscure && !_revealed,
                  keyboardType: widget.keyboardType,
                  textInputAction: widget.textInputAction,
                  autofillHints: widget.autofillHints,
                  onChanged: widget.onChanged,
                  onSubmitted: widget.onSubmitted,
                  style: FanType.body,
                  cursorColor: FanColors.primary,
                  decoration: InputDecoration(
                    isDense: true,
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    disabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: FanSpacing.lg,
                      vertical: FanSpacing.lg,
                    ),
                    hintText: widget.hintText,
                    hintStyle: FanType.body.copyWith(
                      color: FanColors.textPlaceholder,
                    ),
                  ),
                ),
              ),
              if (widget.obscure)
                Semantics(
                  button: true,
                  label: _revealed
                      ? 'Masquer le mot de passe'
                      : 'Afficher le mot de passe',
                  child: InkWell(
                    onTap: widget.enabled
                        ? () => setState(() => _revealed = !_revealed)
                        : null,
                    borderRadius: FanRadius.brMd,
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(
                        minWidth: FanSpacing.minTouchTarget + 24,
                        minHeight: FanSpacing.minTouchTarget,
                      ),
                      child: Center(
                        widthFactor: 1,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: FanSpacing.sm,
                          ),
                          child: Text(
                            _revealed ? 'Masquer' : 'Afficher',
                            style: FanType.body.copyWith(
                              color: FanColors.textPlaceholder,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
        if (hasError) ...<Widget>[
          const SizedBox(height: FanSpacing.xs),
          Semantics(
            liveRegion: true,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Padding(
                  padding: EdgeInsets.only(top: 2),
                  child: Icon(
                    Icons.error_outline,
                    size: 14,
                    color: FanColors.danger,
                  ),
                ),
                const SizedBox(width: FanSpacing.xs),
                Expanded(
                  child: Text(
                    widget.errorText!,
                    style: FanType.caption.copyWith(color: FanColors.danger),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
