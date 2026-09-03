import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/presentation/providers/auth_providers.dart';
import '../../data/datasources/fan_catalog_remote_data_source.dart';
import '../../domain/entities/fan_catalog_category.dart';
import '../../domain/entities/fan_catalog_event.dart';

typedef FanCategoriesLoader = Future<List<FanCatalogCategory>> Function();

typedef FanEventsLoader = Future<List<FanCatalogEvent>> Function(
    String categoryId);

class FanCatalogPage extends ConsumerStatefulWidget {
  const FanCatalogPage({
    this.loadCategories,
    this.loadEvents,
    super.key,
  });

  final FanCategoriesLoader? loadCategories;
  final FanEventsLoader? loadEvents;

  @override
  ConsumerState<FanCatalogPage> createState() => _FanCatalogPageState();
}

class _FanCatalogPageState extends ConsumerState<FanCatalogPage> {
  late Future<List<FanCatalogCategory>> _categories;

  FanCatalogCategory? _selectedCategory;
  Future<List<FanCatalogEvent>>? _events;

  @override
  void initState() {
    super.initState();
    _categories = _loadCategories();
  }

  FanCatalogRemoteDataSource _remoteDataSource() {
    return FanCatalogRemoteDataSource(
      ref.read(dioClientProvider).dio,
    );
  }

  Future<List<FanCatalogCategory>> _loadCategories() {
    final injected = widget.loadCategories;

    if (injected != null) {
      return injected();
    }

    return _remoteDataSource().fetchCategories();
  }

  Future<List<FanCatalogEvent>> _loadEvents(
    String categoryId,
  ) {
    final injected = widget.loadEvents;

    if (injected != null) {
      return injected(categoryId);
    }

    return _remoteDataSource().fetchEvents(categoryId);
  }

  Future<void> _refreshCategories() async {
    final next = _loadCategories();

    setState(() {
      _categories = next;
      _selectedCategory = null;
      _events = null;
    });

    await next;
  }

  Future<void> _refreshEvents() async {
    final category = _selectedCategory;

    if (category == null) {
      return;
    }

    final next = _loadEvents(category.id);

    setState(() {
      _events = next;
    });

    await next;
  }

  void _selectCategory(FanCatalogCategory category) {
    setState(() {
      _selectedCategory = category;
      _events = _loadEvents(category.id);
    });
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

  Widget _categoryCard(FanCatalogCategory category) {
    return Card(
      key: ValueKey<String>(
        'fan-category-${category.id}',
      ),
      child: ListTile(
        leading: const Icon(Icons.category_outlined),
        title: Text(category.name),
        subtitle: category.description.trim().isEmpty
            ? null
            : Text(category.description),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => _selectCategory(category),
      ),
    );
  }

  Widget _categoriesContent(
    AsyncSnapshot<List<FanCatalogCategory>> snapshot,
  ) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (snapshot.hasError) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(
                Icons.cloud_off_outlined,
                size: 64,
              ),
              const SizedBox(height: 16),
              const Text(
                'Impossible de charger le catalogue.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _refreshCategories,
                icon: const Icon(Icons.refresh),
                label: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      );
    }

    final categories = snapshot.data ?? const <FanCatalogCategory>[];

    if (categories.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Aucune catégorie disponible.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refreshCategories,
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(
          16,
          16,
          16,
          32,
        ),
        itemCount: categories.length + 1,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                'Choisissez une catégorie',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            );
          }

          return _categoryCard(
            categories[index - 1],
          );
        },
      ),
    );
  }

  Widget _statusBadge(FanCatalogEvent event) {
    return Chip(
      label: Text(
        event.statusLabel,
        key: ValueKey<String>(
          'fan-event-status-${event.id}',
        ),
      ),
    );
  }

  Widget _eventCard(FanCatalogEvent event) {
    return Card(
      key: ValueKey<String>(
        'fan-event-${event.id}',
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
            if (event.description.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(event.description.trim()),
            ],
            const SizedBox(height: 12),
            Text(
              'Début : ${_formatDate(event.startsAt)}\n'
              'Fin : ${_formatDate(event.endsAt)}',
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
            if (event.capacityTotal != null) ...[
              const SizedBox(height: 12),
              Text(
                'Capacité : ${event.capacityTotal}',
              ),
            ],
            if (event.lifecycleReason.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                switch (event.status.toUpperCase()) {
                  'PUBLISHED' =>
                    'Information : ${event.lifecycleReason.trim()}',
                  'POSTPONED' =>
                    'Motif du report : ${event.lifecycleReason.trim()}',
                  'SUSPENDED' =>
                    'Motif de suspension : ${event.lifecycleReason.trim()}',
                  'CANCELLED' =>
                    'Motif d’annulation : ${event.lifecycleReason.trim()}',
                  _ => 'Information : ${event.lifecycleReason.trim()}',
                },
              ),
            ],
            if (event.isPostponed) ...[
              const SizedBox(height: 12),
              Text(
                event.postponedToStartsAt == null
                    ? 'Nouvelle date : pas encore renseignée par '
                        'l’organisateur.'
                    : 'Nouvelle date : '
                        '${_formatDate(event.postponedToStartsAt)}',
              ),
            ],
            if (event.status.toUpperCase() == 'SUSPENDED') ...[
              const SizedBox(height: 12),
              Text(
                event.postponedToStartsAt == null
                    ? 'Nouvelle date : pas encore renseignée par '
                        'l’organisateur.'
                    : 'Nouvelle date : '
                        '${_formatDate(event.postponedToStartsAt)}',
              ),
            ],
            if (event.isPostponed && event.postponedFromStartsAt != null) ...[
              const SizedBox(height: 12),
              Text(
                'Date initiale : '
                '${_formatDate(event.postponedFromStartsAt)}',
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _eventsContent(
    AsyncSnapshot<List<FanCatalogEvent>> snapshot,
  ) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (snapshot.hasError) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(
                Icons.cloud_off_outlined,
                size: 64,
              ),
              const SizedBox(height: 16),
              const Text(
                'Impossible de charger les événements.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _refreshEvents,
                icon: const Icon(Icons.refresh),
                label: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      );
    }

    final events = (snapshot.data ?? const <FanCatalogEvent>[])
        .where(
          (event) => event.status.toUpperCase() != 'ARCHIVED',
        )
        .toList(growable: false);

    if (events.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Aucun événement dans cette catégorie.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refreshEvents,
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(
          16,
          16,
          16,
          32,
        ),
        itemCount: events.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (_, index) => _eventCard(events[index]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selectedCategory;
    final events = _events;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          selected == null ? 'Catalogue' : selected.name,
        ),
        leading: selected == null
            ? null
            : IconButton(
                tooltip: 'Catégories',
                icon: const Icon(Icons.arrow_back),
                onPressed: () {
                  setState(() {
                    _selectedCategory = null;
                    _events = null;
                  });
                },
              ),
        actions: <Widget>[
          IconButton(
            tooltip: 'Actualiser',
            icon: const Icon(Icons.refresh),
            onPressed: selected == null ? _refreshCategories : _refreshEvents,
          ),
        ],
      ),
      body: SafeArea(
        child: selected == null
            ? FutureBuilder<List<FanCatalogCategory>>(
                future: _categories,
                builder: (context, snapshot) => _categoriesContent(snapshot),
              )
            : FutureBuilder<List<FanCatalogEvent>>(
                future: events,
                builder: (context, snapshot) => _eventsContent(snapshot),
              ),
      ),
    );
  }
}
