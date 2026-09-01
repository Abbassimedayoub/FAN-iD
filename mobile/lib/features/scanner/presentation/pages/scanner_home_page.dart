import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../auth/domain/entities/login_session.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/pages/account_page.dart';

class ScannerHomePage extends ConsumerStatefulWidget {
  const ScannerHomePage({required this.user, super.key});

  final AuthUser user;

  @override
  ConsumerState<ScannerHomePage> createState() => _ScannerHomePageState();
}

class _ScannerHomePageState extends ConsumerState<ScannerHomePage> {
  late final MobileScannerController _scannerController;

  String? _lastCode;
  bool _scanLocked = false;

  @override
  void initState() {
    super.initState();

    _scannerController = MobileScannerController(
      facing: CameraFacing.back,
      formats: const <BarcodeFormat>[BarcodeFormat.qrCode],
      detectionSpeed: DetectionSpeed.noDuplicates,
      autoZoom: true,
    );
  }

  void _onDetect(BarcodeCapture capture) {
    if (_scanLocked || capture.barcodes.isEmpty) {
      return;
    }

    final String? value = capture.barcodes.first.rawValue;

    if (value == null || value.trim().isEmpty) {
      return;
    }

    setState(() {
      _scanLocked = true;
      _lastCode = value;
    });

    unawaited(_scannerController.stop());
  }

  void _scanNext() {
    setState(() {
      _lastCode = null;
      _scanLocked = false;
    });

    unawaited(_scannerController.start());
  }

  @override
  void dispose() {
    unawaited(_scannerController.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF061323),
      appBar: AppBar(
        backgroundColor: const Color(0xFF061323),
        foregroundColor: Colors.white,
        title: const Text('Scanner FAN-iD'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Flash',
            icon: const Icon(Icons.flashlight_on_outlined),
            onPressed: () {
              unawaited(_scannerController.toggleTorch());
            },
          ),
          IconButton(
            tooltip: 'Mon compte',
            icon: const Icon(Icons.person_outline),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => AccountPage(user: widget.user),
                ),
              );
            },
          ),
          IconButton(
            tooltip: 'Se déconnecter',
            icon: const Icon(Icons.logout),
            onPressed: () {
              ref.read(authControllerProvider.notifier).signOutLocal();
            },
          ),
        ],
      ),
      body: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          MobileScanner(controller: _scannerController, onDetect: _onDetect),
          IgnorePointer(
            child: Center(
              child: Container(
                width: 270,
                height: 270,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: const Color(0xFF00D4FF), width: 4),
                ),
              ),
            ),
          ),
          Positioned(
            left: 20,
            right: 20,
            bottom: 30,
            child: SafeArea(
              child: Card(
                color: const Color(0xEEFFFFFF),
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: _lastCode == null
                      ? const Column(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            Icon(Icons.qr_code_scanner, size: 38),
                            SizedBox(height: 10),
                            Text(
                              'Placez le QR code du billet dans le cadre',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        )
                      : Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            const Row(
                              children: <Widget>[
                                Icon(
                                  Icons.check_circle,
                                  color: Colors.green,
                                  size: 32,
                                ),
                                SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    'QR détecté',
                                    style: TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            const Text(
                              'Lecture locale réussie. La validation du billet '
                              'sera connectée à l’API ticketing.',
                            ),
                            const SizedBox(height: 10),
                            Text(
                              _lastCode!,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 12,
                              ),
                            ),
                            const SizedBox(height: 16),
                            FilledButton.icon(
                              onPressed: _scanNext,
                              icon: const Icon(Icons.qr_code_scanner),
                              label: const Text('Scanner le suivant'),
                            ),
                          ],
                        ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
