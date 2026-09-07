import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../../core/errors/failure.dart';
import '../../data/datasources/ticket_admission_remote_data_source.dart';
import '../../../auth/domain/entities/login_session.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
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
  String? _validationError;
  bool _scanLocked = false;
  bool _validationInProgress = false;
  ScannerAdmissionResult? _admission;

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

    final value = capture.barcodes.first.rawValue?.trim();
    if (value == null || value.isEmpty) {
      return;
    }

    setState(() {
      _scanLocked = true;
      _validationInProgress = true;
      _lastCode = value;
      _validationError = null;
      _admission = null;
    });

    unawaited(_scannerController.stop());
    unawaited(_validate(value));
  }

  Future<void> _validate(String token) async {
    try {
      final admission = await TicketAdmissionRemoteDataSource(
        ref.read(authRuntimeProvider).dioClient.dio,
      ).admit(token);

      if (!mounted) {
        return;
      }

      setState(() {
        _admission = admission;
        _validationInProgress = false;
      });
    } on Failure catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _validationError = error.message;
        _validationInProgress = false;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }

      setState(() {
        _validationError = 'Impossible de vérifier ce billet.';
        _validationInProgress = false;
      });
    }
  }

  void _scanNext() {
    setState(() {
      _lastCode = null;
      _validationError = null;
      _admission = null;
      _scanLocked = false;
      _validationInProgress = false;
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
                  border: Border.all(
                    color: const Color(0xFF00D4FF),
                    width: 4,
                  ),
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
                  child: _buildStatusCard(),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusCard() {
    if (_lastCode == null) {
      return const Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(Icons.qr_code_scanner, size: 38),
          SizedBox(height: 10),
          Text(
            'Placez le QR code du billet dans le cadre',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
          ),
        ],
      );
    }

    if (_validationInProgress) {
      return const Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          CircularProgressIndicator(),
          SizedBox(height: 14),
          Text(
            'Vérification du billet…',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
        ],
      );
    }

    final admitted = _admission != null;
    final color = admitted ? Colors.green : Colors.red;
    final title = admitted ? 'Entrée autorisée' : 'Entrée refusée';
    final message = admitted
        ? 'Billet validé. Vous pouvez laisser entrer cette personne.'
        : (_validationError ?? 'Billet non valide.');

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Icon(
              admitted ? Icons.check_circle : Icons.cancel,
              color: color,
              size: 34,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                title,
                style: TextStyle(
                  color: color,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text(message),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _scanNext,
          icon: const Icon(Icons.qr_code_scanner),
          label: const Text('Scanner le suivant'),
        ),
      ],
    );
  }
}
