import 'package:fanid_mobile/features/auth/data/storage/device_fingerprint_store.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('creates and persists a 64-char lowercase hex fingerprint', () async {
    final store = DeviceFingerprintStore(
      randomBytes: (_) => List.generate(32, (index) => index),
    );

    final fingerprint = await store.getOrCreate();

    expect(fingerprint, hasLength(64));
    expect(fingerprint, matches(RegExp(r'^[0-9a-f]{64}$')));

    final persisted = await const FlutterSecureStorage()
        .read(key: DeviceFingerprintStore.fingerprintKey);
    expect(persisted, fingerprint);
  });

  test('reuses the existing fingerprint', () async {
    final existing = 'a' * 64;
    FlutterSecureStorage.setMockInitialValues({
      DeviceFingerprintStore.fingerprintKey: existing,
    });

    final store = DeviceFingerprintStore(
      randomBytes: (_) => throw StateError('must not generate'),
    );

    expect(await store.getOrCreate(), existing);
  });

  test('rejects a generator returning the wrong byte count', () async {
    final store = DeviceFingerprintStore(
      randomBytes: (_) => [1, 2, 3],
    );

    await expectLater(store.getOrCreate(), throwsStateError);
  });

  test('default generator creates a valid fingerprint', () async {
    final store = DeviceFingerprintStore();

    final fingerprint = await store.getOrCreate();

    expect(fingerprint, hasLength(64));
    expect(fingerprint, matches(RegExp(r'^[0-9a-f]{64}$')));
  });
}
