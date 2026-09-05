import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'le catalogue Fan actualise silencieusement les événements',
    () {
      final source = File(
        'lib/features/catalog/presentation/pages/'
        'fan_catalog_page.dart',
      ).readAsStringSync();

      expect(
        source,
        contains('with WidgetsBindingObserver'),
      );

      expect(
        source,
        contains('Duration(seconds: 30)'),
      );

      expect(
        source,
        contains('Timer.periodic('),
      );

      expect(
        source,
        contains(
          'state == AppLifecycleState.resumed',
        ),
      );

      expect(
        source,
        contains('_refreshEventsInBackground()'),
      );

      expect(
        source,
        contains(
          '_selectedCategory?.id != category.id',
        ),
      );

      expect(
        source,
        contains(
          'Future<List<FanCatalogEvent>>.value',
        ),
      );

      expect(
        source,
        contains('_automaticRefreshTimer?.cancel()'),
      );

      expect(
        source,
        contains(
          'WidgetsBinding.instance.removeObserver(this)',
        ),
      );

      expect(
        source,
        contains('_revalidateCartWithEvents(events)'),
      );

      expect(
        source,
        contains('removeItemsForUnavailableEvents'),
      );

      expect(
        source,
        contains('showMaterialBanner'),
      );

      expect(
        source,
        contains('hideCurrentMaterialBanner'),
      );
    },
  );
}
