import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/domain/entities/login_session.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/pages/account_page.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../data/datasources/organizer_events_remote_data_source.dart';
import '../../domain/entities/organizer_event.dart';

typedef OrganizerEventsLoader = Future<List<OrganizerMobileEvent>> Function();

class OrganizerHomePage extends ConsumerStatefulWidget {
  const OrganizerHomePage({
    required this.user,
    this.loadEvents,
    super.key,
  });

  final AuthUser user;
  final OrganizerEventsLoader? loadEvents;

  @override
  ConsumerState<OrganizerHomePage> createState() => _OrganizerHomePageState();
}

class _OrganizerHomePageState extends ConsumerState<OrganizerHomePage> {
  late Future<List<OrganizerMobileEvent>> _events;

  @override
  void initState() {
    super.initState();
    _events = _loadEvents();
  }

  Future<List<OrganizerMobileEvent>> _loadEvents() {
    final injectedLoader = widget.loadEvents;

    if (injectedLoader != null) {
      return injectedLoader();
    }

    return OrganizerEventsRemoteDataSource(
      ref.read(dioClientProvider).dio,
    ).fetchAll();
  }

  Future<void> _refresh() async {
    final next = _loadEvents();

    setState(() {
      _events = next;
    });

    await next;
  }

  String _formatDate(DateTime? value) {
    if (value == null) {
      return 'Date non renseignée';
    }

    final local = value.toLocal();

    String twoDigits(int number) => number.toString().padLeft(2, '0');

    return '${twoDigits(local.day)}/'
        '${twoDigits(local.month)}/'
        '${local.year} à '
        '${twoDigits(local.hour)}:'
        '${twoDigits(local.minute)}';
  }

  Widget _statusBadge(OrganizerMobileEvent event) {
    return Chip(
      avatar: const Icon(
        Icons.circle,
        size: 10,
      ),
      label: Text(
        event.statusLabel,
        key: ValueKey<String>(
          'event-status-${event.id}',
        ),
      ),
    );
  }

  Widget _eventCard(OrganizerMobileEvent event) {
    return Card(
      key: ValueKey<String>(
        'organizer-event-${event.id}',
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
                  Icons.event_outlined,
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
                const SizedBox(width: 8),
                _statusBadge(event),
              ],
            ),
            const SizedBox(height: 14),
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
                    'Début : '
                    '${_formatDate(event.startsAt)}\n'
                    'Fin : '
                    '${_formatDate(event.endsAt)}',
                  ),
                ),
              ],
            ),
            if (event.venue.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              Row(
                children: <Widget>[
                  const Icon(
                    Icons.location_on_outlined,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(event.venue),
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
          ],
        ),
      ),
    );
  }

  Widget _content(
    AsyncSnapshot<List<OrganizerMobileEvent>> snapshot,
  ) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return ListView(
        physics: AlwaysScrollableScrollPhysics(),
        children: <Widget>[
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
          const SizedBox(height: 20),
          Text(
            'Impossible de charger vos événements.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
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

    final events = snapshot.data ?? const <OrganizerMobileEvent>[];

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
          const SizedBox(height: 20),
          Text(
            'Aucun événement',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          const Text(
            'Vos événements apparaîtront ici '
            'avec leur statut opérationnel.',
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
        32,
      ),
      itemCount: events.length + 1,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        if (index == 0) {
          return Padding(
            padding: const EdgeInsets.only(
              bottom: 4,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Mes événements',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${events.length} événement'
                  '${events.length > 1 ? 's' : ''}',
                ),
              ],
            ),
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
        title: const Text('FAN-iD Organisateur'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Actualiser',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
          IconButton(
            tooltip: 'Mon compte',
            icon: const Icon(Icons.person_outline),
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
            icon: const Icon(Icons.logout),
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
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: FutureBuilder<List<OrganizerMobileEvent>>(
            future: _events,
            builder: (context, snapshot) => _content(snapshot),
          ),
        ),
      ),
    );
  }
}
