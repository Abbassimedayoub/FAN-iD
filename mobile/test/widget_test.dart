import 'package:flutter_test/flutter_test.dart';
import 'package:fanid_mobile/main.dart';

void main() {
  test('FAN-iD application smoke test', () {
    const app = FanIdApp();
    expect(app, isA<FanIdApp>());
  });
}
