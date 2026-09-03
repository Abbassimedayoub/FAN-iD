import 'package:fanid_mobile/features/auth/data/storage/token_store.dart';
import 'package:fanid_mobile/features/auth/presentation/controllers/auth_controller.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeTokenStore extends TokenStore {
  int clearCalls = 0;

  @override
  Future<void> clear() async {
    clearCalls += 1;
  }
}

void main() {
  test('a fresh mobile process starts logged out and clears old tokens',
      () async {
    final tokenStore = _FakeTokenStore();

    final container = ProviderContainer(
      overrides: [
        tokenStoreProvider.overrideWithValue(tokenStore),
      ],
    );
    addTearDown(container.dispose);

    final session = await container.read(authControllerProvider.future);

    expect(session, isNull);
    expect(tokenStore.clearCalls, 1);
  });
}
