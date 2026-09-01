// PORTAGE : remplacer `fanid_mobile` par le nom de paquet reel du depot
// (celui declare dans `pubspec.yaml`). Une seule commande suffit :
//   grep -rl 'package:fanid_mobile/' test | xargs sed -i 's/fanid_mobile/<nom>/'
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests du design system.
///
/// Ils ne verifient pas « que ca s affiche » : ils verifient les INVARIANTS
/// qui protegent la fidelite a la maquette et l accessibilite. Un test qui
/// echoue ici signale une derive, pas un pixel deplace.
void main() {
  group('Tokens issus de DS-01', () {
    test('les couleurs libellees valent exactement celles de la planche', () {
      // Ces sept valeurs sont ecrites noir sur blanc sur la maquette.
      expect(FanColors.navy, const Color(0xFF0E2A4D));
      expect(FanColors.primary, const Color(0xFF1663C7));
      expect(FanColors.cyan, const Color(0xFF22D3EE));
      expect(FanColors.teal, const Color(0xFF0EA5B7));
      expect(FanColors.success, const Color(0xFF16B981));
      expect(FanColors.danger, const Color(0xFFEF4444));
      expect(FanColors.warning, const Color(0xFFF59E0B));
    });

    test('le degrade de marque va du cyan vers le bleu', () {
      expect(
        FanColors.brandGradient.colors,
        <Color>[FanColors.cyan, FanColors.primary],
      );
    });

    test('l echelle typographique respecte 28 / 22 / 18 / 15 / 12', () {
      expect(FanType.h1.fontSize, 28);
      expect(FanType.h2.fontSize, 22);
      expect(FanType.h3.fontSize, 18);
      expect(FanType.body.fontSize, 15);
      expect(FanType.caption.fontSize, 12);
    });

    test('aucune police n est chargee a l execution', () {
      // Les familles sont resolues depuis les assets embarques. Si un jour
      // quelqu un reintroduit `google_fonts`, le nom de famille cesserait
      // d etre exactement « Sora » / « Inter » et ce test le dirait.
      expect(FanType.h1.fontFamily, 'Sora');
      expect(FanType.body.fontFamily, 'Inter');
      expect(FanType.headingFamily, 'Sora');
      expect(FanType.bodyFamily, 'Inter');
    });

    test('l echelle d espacement ne contient que les pas prevus', () {
      expect(
        <double>[
          FanSpacing.xs,
          FanSpacing.sm,
          FanSpacing.md,
          FanSpacing.lg,
          FanSpacing.xl,
          FanSpacing.xxl,
          FanSpacing.xxxl,
        ],
        <double>[4, 8, 12, 16, 20, 24, 32],
      );
    });

    test('la cible tactile minimale reste a 48 dp', () {
      expect(FanSpacing.minTouchTarget, 48);
    });
  });

  group('Theme', () {
    test('le theme relaie les couleurs de marque et la police de corps', () {
      final ThemeData theme = FanTheme.light;
      expect(theme.colorScheme.primary, FanColors.primary);
      expect(theme.colorScheme.secondary, FanColors.cyan);
      expect(theme.colorScheme.error, FanColors.danger);
      expect(theme.scaffoldBackgroundColor, FanColors.background);
      expect(theme.textTheme.bodyMedium?.fontFamily, 'Inter');
    });

    testWidgets('le theme ne borne pas l echelle de texte de l utilisateur',
        (WidgetTester tester) async {
      // Regression : une version anterieure clampait `textScaler` a 1.3, ce
      // qui ecrasait le reglage systeme d un utilisateur malvoyant
      // (WCAG 2.1 §1.4.4 demande 200 %).
      late TextScaler observed;
      await tester.pumpWidget(
        MaterialApp(
          theme: FanTheme.light,
          home: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(2)),
            child: Builder(
              builder: (BuildContext context) {
                observed = MediaQuery.textScalerOf(context);
                return const SizedBox.shrink();
              },
            ),
          ),
        ),
      );
      expect(observed.scale(10), 20);
    });
  });

  group('Cibles tactiles — 48 dp minimum', () {
    // Ces tests manquaient a la premiere version du bundle, et c est
    // exactement pour cela que `FanIdFilterChip` avait pu naitre a 40 dp sans
    // que rien ne proteste. Un invariant qu aucun test ne garde n est pas un
    // invariant, c est une intention.

    Future<Size> pumpAndMeasure(WidgetTester tester, Widget child) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: FanTheme.light,
          home: Scaffold(
            body: Align(alignment: Alignment.topLeft, child: child),
          ),
        ),
      );
      return tester.getSize(find.byWidget(child));
    }

    testWidgets('bouton primaire', (WidgetTester tester) async {
      final Size size = await pumpAndMeasure(
        tester,
        FanIdPrimaryButton(label: 'Se connecter', onPressed: () {}),
      );
      expect(size.height, greaterThanOrEqualTo(FanSpacing.minTouchTarget));
    });

    testWidgets('bouton secondaire', (WidgetTester tester) async {
      final Size size = await pumpAndMeasure(
        tester,
        FanIdSecondaryButton(label: 'Annuler', onPressed: () {}),
      );
      expect(size.height, greaterThanOrEqualTo(FanSpacing.minTouchTarget));
    });

    testWidgets('bouton danger', (WidgetTester tester) async {
      final Size size = await pumpAndMeasure(
        tester,
        FanIdDangerButton(label: 'Supprimer', onPressed: () {}),
      );
      expect(size.height, greaterThanOrEqualTo(FanSpacing.minTouchTarget));
    });

    testWidgets('lien', (WidgetTester tester) async {
      final Size size = await pumpAndMeasure(
        tester,
        FanIdLinkButton(label: 'Mot de passe oublié ?', onPressed: () {}),
      );
      expect(size.height, greaterThanOrEqualTo(FanSpacing.minTouchTarget));
    });

    testWidgets('chip de filtre, malgre une pastille dessinee a 40 dp',
        (WidgetTester tester) async {
      final Size size = await pumpAndMeasure(
        tester,
        FanIdFilterChip(label: 'Football', selected: true, onPressed: () {}),
      );
      expect(size.height, greaterThanOrEqualTo(FanSpacing.minTouchTarget));
    });

    testWidgets('bouton rond, meme avec un disque demande a 40 dp',
        (WidgetTester tester) async {
      final Size size = await pumpAndMeasure(
        tester,
        FanIdCircleButton(
          icon: Icons.close,
          tooltip: 'Quitter',
          size: 40,
          onPressed: () {},
        ),
      );
      expect(size.height, greaterThanOrEqualTo(FanSpacing.minTouchTarget));
      expect(size.width, greaterThanOrEqualTo(FanSpacing.minTouchTarget));
    });
  });

  group('Bouton primaire — actif / desactive / chargement', () {
    testWidgets('actif : le tap remonte bien', (WidgetTester tester) async {
      int taps = 0;
      await tester.pumpWidget(
        MaterialApp(
          theme: FanTheme.light,
          home: Scaffold(
            body: FanIdPrimaryButton(
              label: 'Se connecter',
              onPressed: () => taps++,
            ),
          ),
        ),
      );
      await tester.tap(find.byType(FanIdPrimaryButton));
      expect(taps, 1);
    });

    testWidgets('desactive : inerte et annonce comme tel',
        (WidgetTester tester) async {
      int taps = 0;
      await tester.pumpWidget(
        MaterialApp(
          theme: FanTheme.light,
          home: Scaffold(
            body: FanIdPrimaryButton(
              label: 'Épuisé',
              onPressed: null,
              // ignore: avoid_redundant_argument_values
              loading: false,
            ),
          ),
        ),
      );
      await tester.tap(find.byType(FanIdPrimaryButton));
      expect(taps, 0);
      expect(
        tester.widget<InkWell>(find.byType(InkWell)).onTap,
        isNull,
      );
    });

    testWidgets('chargement : indicateur visible ET tap ignore',
        (WidgetTester tester) async {
      int taps = 0;
      await tester.pumpWidget(
        MaterialApp(
          theme: FanTheme.light,
          home: Scaffold(
            body: FanIdPrimaryButton(
              label: 'Se connecter',
              loading: true,
              onPressed: () => taps++,
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.tap(find.byType(FanIdPrimaryButton));
      // `onPressed` est fourni, mais `loading` doit primer : c est le coeur de
      // la protection contre la double soumission.
      expect(taps, 0);
    });
  });

  group('Champ de saisie', () {
    testWidgets('champ normal : ni message ni icone d erreur',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FanIdTextField(label: 'Email', hintText: 'nom@exemple.fr'),
          ),
        ),
      );
      expect(find.text('Email'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsNothing);
    });

    testWidgets(
        'champ en erreur : message texte + icone, pas seulement une '
        'couleur', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FanIdTextField(
              label: 'Mot de passe',
              errorText: 'Mot de passe incorrect. Réessayez.',
            ),
          ),
        ),
      );
      expect(find.text('Mot de passe incorrect. Réessayez.'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('la touche Entree declenche onSubmitted quand il est fourni',
        (WidgetTester tester) async {
      int submits = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FanIdTextField(
              label: 'Mot de passe',
              obscure: true,
              onSubmitted: (String _) => submits++,
            ),
          ),
        ),
      );
      await tester.tap(find.byType(TextField).first);
      await tester.pump();
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pump();
      expect(submits, 1);
    });

    testWidgets('la touche Entree est inerte quand onSubmitted est null',
        (WidgetTester tester) async {
      // C est le mecanisme exact par lequel `LoginView` empeche une seconde
      // soumission pendant le chargement. Griser le bouton ne suffit pas.
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FanIdTextField(label: 'Mot de passe', obscure: true),
          ),
        ),
      );
      await tester.tap(find.byType(TextField).first);
      await tester.pump();
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pump();
      expect(tester.takeException(), isNull);
    });
  });

  group('Badges de statut', () {
    test('les six statuts de DS-01 sont presents, et seulement eux', () {
      expect(FanBadgeStatus.values.length, 6);
      expect(
        FanBadgeStatus.values
            .map((FanBadgeStatus s) => s.defaultLabel)
            .toList(),
        <String>[
          'Valide',
          'Utilisé',
          'Transféré',
          'En attente',
          'EN DIRECT',
          'Épuisé',
        ],
      );
    });

    testWidgets('un badge affiche son libelle par defaut',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: FanIdBadge(status: FanBadgeStatus.valide)),
        ),
      );
      expect(find.text('Valide'), findsOneWidget);
    });
  });
}
