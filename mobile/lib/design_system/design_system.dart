/// Point d entree unique du design system FAN iD.
///
/// Les vues importent CE fichier, et rien d autre du dossier
/// `design_system/`. C est ce qui rend le portage mecanique : un seul chemin
/// a reecrire dans le vrai depot.
///
/// Le design system ne depend de RIEN d autre que Flutter :
/// pas de `google_fonts`, pas de `go_router`, pas de Riverpod, pas de Dio,
/// aucune donnee simulee. Il est copiable tel quel.
library;

export 'colors.dart';
export 'radius.dart';
export 'shadows.dart';
export 'spacing.dart';
export 'theme.dart';
export 'typography.dart';
export 'widgets/fanid_badge.dart';
export 'widgets/fanid_buttons.dart';
export 'widgets/fanid_logo.dart';
export 'widgets/fanid_state_views.dart';
export 'widgets/fanid_text_field.dart';
