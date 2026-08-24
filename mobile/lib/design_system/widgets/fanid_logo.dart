import 'package:flutter/material.dart';

import '../colors.dart';
import '../radius.dart';
import '../spacing.dart';
import '../typography.dart';

/// Logo officiel FAN iD.
///
/// ## Le fichier n est PAS livre dans ce bundle
///
/// Le logo officiel existe deja dans le depot FAN iD. Le dupliquer ici
/// creerait une seconde copie qui divergerait a la premiere retouche. Ce
/// widget se contente de le referencer par [assetPath] — voir
/// `PORTING_MANIFEST.md` pour l emplacement attendu et la ligne `pubspec.yaml`
/// correspondante.
///
/// Le logo n est ni redessine, ni recolorise, ni approxime : le composant se
/// contente de le poser.
///
/// ## Repli explicite
///
/// Si l asset est absent ou mal declare, [errorBuilder] affiche un cartouche
/// neutre au lieu de laisser exploser une exception de rendu. Un chemin
/// d asset mal configure doit produire un ecran degrade lisible, pas un ecran
/// rouge — et cela rend aussi les tests de widget deterministes.
class FanIdLogo extends StatelessWidget {
  const FanIdLogo({this.size = 96, super.key});

  final double size;

  /// Emplacement attendu du logo dans le depot FAN iD.
  static const String assetPath = 'assets/images/fanid_logo.png';

  @override
  Widget build(BuildContext context) {
    final BorderRadius radius = BorderRadius.circular(size * 0.22);

    return Semantics(
      label: 'Logo FAN iD',
      image: true,
      child: ClipRRect(
        borderRadius: radius,
        child: Image.asset(
          assetPath,
          width: size,
          height: size,
          fit: BoxFit.cover,
          errorBuilder:
              (BuildContext context, Object error, StackTrace? stack) {
            return Container(
              width: size,
              height: size,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                gradient: FanColors.brandGradient,
                borderRadius: radius,
              ),
              child: Icon(
                Icons.confirmation_number_outlined,
                size: size * 0.5,
                color: Colors.white,
              ),
            );
          },
        ),
      ),
    );
  }
}

/// Mot-symbole « FANID », en Sora tres espace, avec le degrade de marque
/// applique au texte.
class FanIdWordmark extends StatelessWidget {
  const FanIdWordmark({this.fontSize = 34, super.key});

  final double fontSize;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'FAN iD',
      excludeSemantics: true,
      child: ShaderMask(
        shaderCallback: (Rect bounds) =>
            FanColors.brandGradient.createShader(bounds),
        child: Text(
          'FANID',
          textAlign: TextAlign.center,
          style: FanType.wordmark.copyWith(
            fontSize: fontSize,
            color: Colors.white,
          ),
        ),
      ),
    );
  }
}

/// Marque compacte : logo + mot-symbole, pour les en-tetes clairs.
class FanIdBrandRow extends StatelessWidget {
  const FanIdBrandRow({this.logoSize = 40, super.key});

  final double logoSize;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        FanIdLogo(size: logoSize),
        const SizedBox(width: FanSpacing.sm),
        Text('FANID', style: FanType.h3.copyWith(letterSpacing: 3)),
      ],
    );
  }
}

/// Fond sombre degrade, partage par les ecrans immersifs (splash, QR,
/// scanner). Pose ici parce qu il fait partie de l identite, pas d un ecran.
class NavyBackdrop extends StatelessWidget {
  const NavyBackdrop({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: FanColors.navyGradient),
      child: child,
    );
  }
}

/// Bandeau d information.
///
/// Deux variantes, toutes deux presentes dans la maquette : posee sur un fond
/// navy, ou sur un fond clair ([onLight]).
class NavyNoticeBanner extends StatelessWidget {
  const NavyNoticeBanner({
    required this.icon,
    required this.message,
    this.onLight = false,
    super.key,
  });

  final IconData icon;
  final String message;
  final bool onLight;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: onLight ? FanColors.cyanTint : FanColors.onNavySurface,
        borderRadius: FanRadius.brMd,
        border: Border.all(
          color: onLight ? FanColors.cyan : FanColors.onNavyBorder,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon,
              size: 18, color: onLight ? FanColors.teal : FanColors.cyan),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: FanType.caption.copyWith(
                color: onLight
                    ? FanColors.textSecondary
                    : FanColors.onNavySecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
