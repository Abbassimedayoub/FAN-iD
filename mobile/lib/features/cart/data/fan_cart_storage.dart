import 'package:hive/hive.dart';

abstract interface class FanCartStorage {
  Future<Map<String, dynamic>?> read();

  Future<void> write(
    Map<String, dynamic> value,
  );

  Future<void> clear();
}

class HiveFanCartStorage implements FanCartStorage {
  HiveFanCartStorage({
    required String ownerKey,
  }) : _storageKey = 'cart:${ownerKey.trim().toLowerCase()}';

  static const String _boxName = 'fan_cart_v1';

  final String _storageKey;

  Future<Box<dynamic>>? _boxFuture;

  Future<Box<dynamic>> _box() {
    return _boxFuture ??= Hive.openBox<dynamic>(_boxName);
  }

  @override
  Future<Map<String, dynamic>?> read() async {
    final box = await _box();
    final value = box.get(_storageKey);

    if (value is! Map) {
      return null;
    }

    return Map<String, dynamic>.from(value);
  }

  @override
  Future<void> write(
    Map<String, dynamic> value,
  ) async {
    final box = await _box();

    await box.put(
      _storageKey,
      value,
    );
  }

  @override
  Future<void> clear() async {
    final box = await _box();

    await box.delete(_storageKey);
  }
}
