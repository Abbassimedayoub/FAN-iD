import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../data/fan_ticket_qr_remote_data_source.dart';
import '../../domain/fan_ticket.dart';

class FanTicketQrPage extends ConsumerStatefulWidget {
  const FanTicketQrPage({
    required this.ticket,
    super.key,
  });

  final FanTicket ticket;

  @override
  ConsumerState<FanTicketQrPage> createState() => _FanTicketQrPageState();
}

class _FanTicketQrPageState extends ConsumerState<FanTicketQrPage> {
  FanTicketQr? _qr;
  Object? _error;
  bool _loading = true;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadQr();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadQr() async {
    _refreshTimer?.cancel();

    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final session = ref.read(authControllerProvider).valueOrNull;
      if (session == null || session.access.isEmpty) {
        throw StateError('Session utilisateur indisponible.');
      }

      final qr = await FanTicketQrRemoteDataSource(
        ref.read(dioClientProvider).dio,
      ).fetchQr(
        ticketId: widget.ticket.id,
        accessToken: session.access,
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _qr = qr;
        _loading = false;
      });

      _refreshTimer = Timer(
        Duration(seconds: qr.refreshAfterSeconds),
        _loadQr,
      );
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final qr = _qr;

    return Scaffold(
      backgroundColor: const Color(0xFF0B2545),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0B2545),
        iconTheme: const IconThemeData(color: Colors.white),
        title: const Text('QR dynamique',
            style: TextStyle(color: Color(0xFF7CEBFA))),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 24, 22, 32),
            child: _loading
                ? const CircularProgressIndicator()
                : _error != null
                    ? _QrError(onRetry: _loadQr)
                    : Column(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Text(
                            widget.ticket.eventName,
                            textAlign: TextAlign.center,
                            style: Theme.of(context)
                                .textTheme
                                .titleLarge
                                ?.copyWith(color: Colors.white, fontSize: 20),
                          ),
                          const SizedBox(height: 8),
                          Text(widget.ticket.ticketCategoryName,
                              style: const TextStyle(color: Color(0xFFAECBE8))),
                          const SizedBox(height: 24),
                          Container(
                            constraints: const BoxConstraints(maxWidth: 300),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              border: Border.all(
                                  color: const Color(0xFF22D3EE), width: 3),
                              borderRadius: BorderRadius.circular(32),
                            ),
                            child: Card(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: QrImageView(
                                  key: const ValueKey<String>(
                                      'ticket-dynamic-qr'),
                                  data: qr!.token,
                                  version: QrVersions.auto,
                                  size: 240,
                                  backgroundColor: Colors.white,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 20),
                          const Text(
                            'Ce code est temporaire et se renouvelle automatiquement.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Color(0xFFAECBE8)),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Valide jusqu’à ${_formatTime(qr.expiresAt)}',
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(color: const Color(0xFF22D3EE)),
                          ),
                        ],
                      ),
          ),
        ),
      ),
    );
  }

  static String _formatTime(DateTime value) {
    final time = value.toLocal();

    return '${time.hour.toString().padLeft(2, '0')}:'
        '${time.minute.toString().padLeft(2, '0')}:'
        '${time.second.toString().padLeft(2, '0')}';
  }
}

class _QrError extends StatelessWidget {
  const _QrError({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        const Icon(Icons.error_outline, size: 48, color: Colors.white),
        const SizedBox(height: 16),
        const Text(
          'Impossible de générer le QR dynamique.',
          textAlign: TextAlign.center,
          style: TextStyle(color: Colors.white),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: onRetry,
          child: const Text('Réessayer'),
        ),
      ],
    );
  }
}
