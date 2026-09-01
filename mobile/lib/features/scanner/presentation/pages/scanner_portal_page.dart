import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/domain/entities/login_session.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/pages/account_page.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../data/datasources/scanner_events_remote_data_source.dart';
import '../../domain/entities/scanner_assigned_event.dart';
import 'scanner_home_page.dart';

typedef ScannerAssignedEventsLoader = Future<List<ScannerAssignedEvent>>
    Function();

class ScannerPortalPage extends ConsumerStatefulWidget {
  const ScannerPortalPage({
    required this.user,
    this.loadEvents,
    super.key,
  });

  final AuthUser user;
  final ScannerAssignedEventsLoader? loadEvents;

  @override
  ConsumerState<ScannerPortalPage> createState() => _ScannerPortalPageState();
}

class _ScannerPortalPageState extends ConsumerState<ScannerPortalPage> {
  late Future<List<ScannerAssignedEvent>> _events;

  @override
  void initState() {
    super.initState();
    _events = _loadEvents();
  }

  Future<List<ScannerAssignedEvent>> _loadEvents() {
    final injectedLoader = widget.loadEvents;

    if (injectedLoader != null) {
      return injectedLoader();
    }

    return ScannerEventsRemoteDataSource(
      ref.read(dioClientProvider).dio,
    ).fetchAssignedEvents();
  }

  Future<void> _refresh() async {
    final next = _loadEvents();

    setState(() {
      _events = next;
    });

    await next;
  }

  void _openScanner() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ScannerHomePage(
          user: widget.user,
        ),
      ),
    );
  }

  String _formatDate(DateTime? value) {
    if (value == null) {
      return 'Non renseigné';
    }

    final local = value.toLocal();

    String twoDigits(int value) => value.toString().padLeft(2, '0');

    return '${twoDigits(local.day)}/'
        '${twoDigits(local.month)}/'
        '${local.year} '
        '${twoDigits(local.hour)}:'
        '${twoDigits(local.minute)}';
  }

  String _scheduleText(
    ScannerAssignedEvent event,
  ) {
    if (event.status.toUpperCase() != 'POSTPONED') {
      return 'Début : ${_formatDate(event.startsAt)}\n'
          'Fin : ${_formatDate(event.endsAt)}';
    }

    final oldStart = event.postponedFromStartsAt ?? event.startsAt;

    final oldEnd = event.postponedFromEndsAt ?? event.endsAt;

    final newStart = event.postponedToStartsAt;

    final newEnd = event.postponedToEndsAt;

    final oldSchedule = 'Ancienne date : '
        '${_formatDate(oldStart)} → '
        '${_formatDate(oldEnd)}';

    if (newStart == null || newEnd == null) {
      return '$oldSchedule\n'
          'Nouvelle date : '
          'Nouvelle date à venir';
    }

    return '$oldSchedule\n'
        'Nouvelle date : '
        '${_formatDate(newStart)} → '
        '${_formatDate(newEnd)}';
  }

  Widget _statusChip(
    ScannerAssignedEvent event,
  ) {
    final icon = event.accessInterrupted
        ? Icons.warning_amber_rounded
        : Icons.check_circle_outline;

    return Chip(
      avatar: Icon(
        icon,
        size: 18,
      ),
      label: Text(
        event.statusLabel,
        key: ValueKey<String>(
          'scanner-event-status-${event.id}',
        ),
      ),
    );
  }

  Widget _eventCard(
    ScannerAssignedEvent event,
  ) {
    return Card(
      key: ValueKey<String>(
        'scanner-assigned-event-${event.assignmentId}',
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Icon(
                  Icons.event_available_outlined,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    event.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: _statusChip(event),
            ),
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Icon(
                  Icons.schedule_outlined,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _scheduleText(event),
                  ),
                ),
              ],
            ),
            if (event.venue.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Icon(
                    Icons.location_on_outlined,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      event.venue.trim(),
                    ),
                  ),
                ],
              ),
            ],
            if (event.lifecycleReason.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                'Information : '
                '${event.lifecycleReason.trim()}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (event.accessInterrupted) ...[
              const SizedBox(height: 14),
              const Text(
                'Le statut actuel de cet événement '
                'ne permet pas un accès normal.',
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildContent(
    AsyncSnapshot<List<ScannerAssignedEvent>> snapshot,
  ) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: const <Widget>[
          SizedBox(height: 180),
          Center(
            child: CircularProgressIndicator(),
          ),
        ],
      );
    }

    if (snapshot.hasError) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          const SizedBox(height: 80),
          const Icon(
            Icons.cloud_off_outlined,
            size: 64,
          ),
          const SizedBox(height: 18),
          Text(
            'Impossible de charger vos événements affectés.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          const Text(
            'Vérifiez votre connexion puis réessayez.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
            label: const Text('Réessayer'),
          ),
        ],
      );
    }

    final events = snapshot.data ?? const <ScannerAssignedEvent>[];

    if (events.isEmpty) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          const SizedBox(height: 80),
          const Icon(
            Icons.event_busy_outlined,
            size: 64,
          ),
          const SizedBox(height: 18),
          Text(
            'Aucun événement affecté',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          const Text(
            'Votre organisateur doit vous affecter '
            'à un événement avant qu’il apparaisse ici.',
            textAlign: TextAlign.center,
          ),
        ],
      );
    }

    return ListView.separated(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(
        16,
        16,
        16,
        120,
      ),
      itemCount: events.length + 1,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        if (index == 0) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Mes événements affectés',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                '${events.length} événement'
                '${events.length > 1 ? 's' : ''} affecté'
                '${events.length > 1 ? 's' : ''}',
              ),
              const SizedBox(height: 4),
              const Text(
                'Les changements de statut sont '
                'récupérés depuis FAN-iD.',
              ),
            ],
          );
        }

        return _eventCard(
          events[index - 1],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Scanner FAN-iD',
        ),
        actions: <Widget>[
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refresh,
            icon: const Icon(
              Icons.refresh,
            ),
          ),
          IconButton(
            tooltip: 'Mon compte',
            icon: const Icon(
              Icons.person_outline,
            ),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => AccountPage(
                    user: widget.user,
                  ),
                ),
              );
            },
          ),
          IconButton(
            tooltip: 'Se déconnecter',
            icon: const Icon(
              Icons.logout,
            ),
            onPressed: () {
              ref
                  .read(
                    authControllerProvider.notifier,
                  )
                  .signOutLocal();
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<ScannerAssignedEvent>>(
          future: _events,
          builder: (context, snapshot) => _buildContent(snapshot),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openScanner,
        icon: const Icon(
          Icons.qr_code_scanner,
        ),
        label: const Text(
          'Scanner QR',
        ),
      ),
    );
  }
}
