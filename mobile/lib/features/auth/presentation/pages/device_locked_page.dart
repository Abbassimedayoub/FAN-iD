import 'package:flutter/material.dart';

import '../../../../core/errors/failure.dart';
import '../views/device_locked_view.dart';

class DeviceLockedPage extends StatelessWidget {
  const DeviceLockedPage({
    required this.failure,
    this.onReset,
    this.onBackToLogin,
    super.key,
  });

  final BusinessFailure failure;
  final VoidCallback? onReset;
  final VoidCallback? onBackToLogin;

  @override
  Widget build(BuildContext context) {
    final details = failure.details;

    final rawLabel = details['active_device_label'];
    final rawBoundAt = details['bound_at'];

    return DeviceLockedView(
      activeDeviceLabel:
          rawLabel is String && rawLabel.isNotEmpty ? rawLabel : null,
      boundAtText:
          rawBoundAt is String && rawBoundAt.isNotEmpty ? rawBoundAt : null,
      resetAvailable: details['reset_available'] == true,
      onReset: onReset,
      onBackToLogin: onBackToLogin,
    );
  }
}
