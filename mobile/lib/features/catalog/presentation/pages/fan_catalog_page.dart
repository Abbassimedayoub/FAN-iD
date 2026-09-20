import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../cart/domain/fan_cart.dart';
import '../../../cart/presentation/pages/fan_cart_page.dart';
import '../../../cart/presentation/providers/fan_cart_provider.dart';
import '../../../cart/presentation/widgets/fan_ticket_selection_sheet.dart';
import '../../data/datasources/fan_catalog_remote_data_source.dart';
import '../../domain/entities/fan_catalog_category.dart';
import '../../domain/entities/fan_catalog_event.dart';
import '../../domain/entities/fan_catalog_ticket_category.dart';
import '../../domain/fan_catalog_filters.dart';

typedef FanCategoriesLoader = Future<List<FanCatalogCategory>> Function();

typedef FanEventsLoader = Future<List<FanCatalogEvent>> Function(
    String categoryId);

class FanCatalogPage extends ConsumerStatefulWidget {
  const FanCatalogPage({
    this.loadCategories,
    this.loadEvents,
    this.now,
    this.cartOwnerKey,
    super.key,
  });

  final FanCategoriesLoader? loadCategories;
  final FanEventsLoader? loadEvents;
  final DateTime Function()? now;
  final String? cartOwnerKey;

  @override
  ConsumerState<FanCatalogPage> createState() => _FanCatalogPageState();
}

class _FanCatalogPageState extends ConsumerState<FanCatalogPage>
    with WidgetsBindingObserver {
  static const Duration _automaticRefreshInterval = Duration(seconds: 30);

  late Future<List<FanCatalogCategory>> _categories;

  FanCatalogCategory? _selectedCategory;
  Future<List<FanCatalogEvent>>? _events;
  Timer? _automaticRefreshTimer;

  String? _venueFilter;
  FanCatalogAvailabilityFilter _availabilityFilter =
      FanCatalogAvailabilityFilter.all;
  FanCatalogTimeFilter _timeFilter = FanCatalogTimeFilter.all;

  @override
  void initState() {
    super.initState();

    WidgetsBinding.instance.addObserver(this);

    _categories = _loadCategories();

    _automaticRefreshTimer = Timer.periodic(
      _automaticRefreshInterval,
      (_) {
        unawaited(
          _refreshEventsInBackground(),
        );
      },
    );
  }

  @override
  void didChangeAppLifecycleState(
    AppLifecycleState state,
  ) {
    if (state == AppLifecycleState.resumed) {
      unawaited(
        _refreshEventsInBackground(),
      );
    }
  }

  @override
  void dispose() {
    _automaticRefreshTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
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
  ) async {
    final injected = widget.loadEvents;
    final events = injected != null
        ? await injected(categoryId)
        : await _remoteDataSource().fetchEvents(categoryId);

    if (mounted) {
      await _revalidateCartWithEvents(events);
    }

    return events;
  }

  Future<void> _revalidateCartWithEvents(
    List<FanCatalogEvent> events,
  ) async {
    final ownerKey = widget.cartOwnerKey;

    if (ownerKey == null) {
      return;
    }

    final unavailableEventIds = events
        .where((event) => !event.canPurchaseTickets)
        .map((event) => event.id)
        .where((eventId) => eventId.isNotEmpty);

    final removedCount = await ref
        .read(
          fanCartControllerProvider(ownerKey).notifier,
        )
        .removeItemsForUnavailableEvents(unavailableEventIds);

    if (!mounted || removedCount == 0) {
      return;
    }

    final messenger = ScaffoldMessenger.of(context);

    messenger.hideCurrentMaterialBanner();
    messenger.showMaterialBanner(
      MaterialBanner(
        content: Text(
          '$removedCount billet(s) retiré(s) : '
          'cet événement n’est plus disponible.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: messenger.hideCurrentMaterialBanner,
            child: const Text('Fermer'),
          ),
        ],
      ),
    );
  }

  Future<void> _refreshCategories() async {
    final next = _loadCategories();

    setState(() {
      _categories = next;
      _selectedCategory = null;
      _events = null;
      _resetFilters();
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

  Future<void> _refreshEventsInBackground() async {
    final category = _selectedCategory;

    if (category == null) {
      return;
    }

    try {
      final events = await _loadEvents(
        category.id,
      );

      if (!mounted || _selectedCategory?.id != category.id) {
        return;
      }

      setState(() {
        _events = Future<List<FanCatalogEvent>>.value(
          events,
        );
      });
    } catch (_) {
      // Automatic refresh must never hide an already displayed catalog when the network
      // est temporairement indisponible.
    }
  }

  void _selectCategory(FanCatalogCategory category) {
    setState(() {
      _selectedCategory = category;
      _events = _loadEvents(category.id);
      _resetFilters();
    });
  }

  DateTime _currentTime() {
    return widget.now?.call() ?? DateTime.now();
  }

  void _resetFilters() {
    _venueFilter = null;
    _availabilityFilter = FanCatalogAvailabilityFilter.all;
    _timeFilter = FanCatalogTimeFilter.all;
  }

  String _availabilityFilterLabel(
    FanCatalogAvailabilityFilter filter,
  ) {
    return switch (filter) {
      FanCatalogAvailabilityFilter.all => 'Tous',
      FanCatalogAvailabilityFilter.available => 'Non complet (disponible)',
      FanCatalogAvailabilityFilter.full => 'Complet',
    };
  }

  String _timeFilterLabel(
    FanCatalogTimeFilter filter,
  ) {
    return switch (filter) {
      FanCatalogTimeFilter.all => 'Tous',
      FanCatalogTimeFilter.upcoming => 'À venir',
      FanCatalogTimeFilter.ongoing => 'En cours',
      FanCatalogTimeFilter.finished => 'Terminé',
    };
  }

  Widget _filtersPanel(
    List<FanCatalogEvent> sourceEvents,
    int filteredCount,
  ) {
    final scheme = Theme.of(context).colorScheme;
    final venues = FanCatalogFilters.venues(sourceEvents);
    final hasActiveFilters = _venueFilter != null ||
        _availabilityFilter != FanCatalogAvailabilityFilter.all ||
        _timeFilter != FanCatalogTimeFilter.all;

    Widget filterChip({
      required Key key,
      required String label,
      required bool selected,
      required VoidCallback onSelected,
    }) {
      return ChoiceChip(
        key: key,
        label: Text(label, maxLines: 1),
        selected: selected,
        showCheckmark: selected,
        visualDensity: VisualDensity.compact,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(
            color: selected ? scheme.primary : scheme.outlineVariant,
          ),
        ),
        selectedColor: scheme.primary.withValues(alpha: 0.12),
        backgroundColor: scheme.surface,
        labelStyle: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: selected ? scheme.primary : scheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
            ),
        onSelected: (_) => onSelected(),
      );
    }

    return Card(
      key: const ValueKey<String>('fan-catalog-filters'),
      elevation: 0,
      margin: EdgeInsets.zero,
      color: scheme.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Filtres',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ),
                TextButton.icon(
                  key: const ValueKey<String>('fan-filter-reset'),
                  onPressed:
                      hasActiveFilters ? () => setState(_resetFilters) : null,
                  icon: const Icon(Icons.restart_alt, size: 18),
                  label: const Text('Réinitialiser'),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text('Lieu', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 7),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: <Widget>[
                  filterChip(
                    key: const ValueKey<String>('fan-filter-venue-all'),
                    label: 'Tous les lieux',
                    selected: _venueFilter == null,
                    onSelected: () => setState(() => _venueFilter = null),
                  ),
                  for (final venue in venues) ...<Widget>[
                    const SizedBox(width: 8),
                    filterChip(
                      key: ValueKey<String>('fan-filter-venue-$venue'),
                      label: venue,
                      selected: _venueFilter == venue,
                      onSelected: () => setState(() => _venueFilter = venue),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 13),
            Text(
              'Disponibilité',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 7),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: FanCatalogAvailabilityFilter.values
                  .map(
                    (filter) => filterChip(
                      key: ValueKey<String>(
                        'fan-filter-availability-${filter.name}',
                      ),
                      label: _availabilityFilterLabel(filter),
                      selected: _availabilityFilter == filter,
                      onSelected: () => setState(
                        () => _availabilityFilter = filter,
                      ),
                    ),
                  )
                  .toList(growable: false),
            ),
            const SizedBox(height: 13),
            Text('Période', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 7),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: FanCatalogTimeFilter.values
                  .map(
                    (filter) => filterChip(
                      key: ValueKey<String>(
                        'fan-filter-time-${filter.name}',
                      ),
                      label: _timeFilterLabel(filter),
                      selected: _timeFilter == filter,
                      onSelected: () => setState(() => _timeFilter = filter),
                    ),
                  )
                  .toList(growable: false),
            ),
            const SizedBox(height: 12),
            Text(
              '$filteredCount / ${sourceEvents.length} événements',
              key: const ValueKey<String>('fan-filter-result-count'),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openCart() async {
    final ownerKey = widget.cartOwnerKey;

    if (ownerKey == null) {
      return;
    }

    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => FanCartPage(
          cartOwnerKey: ownerKey,
        ),
      ),
    );
  }

  Future<void> _addToCart(
    FanCatalogEvent event,
    FanCatalogTicketCategory tariff,
    int quantity,
  ) async {
    final ownerKey = widget.cartOwnerKey;

    if (ownerKey == null) {
      return;
    }

    try {
      await ref
          .read(
            fanCartControllerProvider(
              ownerKey,
            ).notifier,
          )
          .addItem(
            FanCartItem(
              eventId: event.id,
              eventName: event.name,
              ticketCategoryId: tariff.id,
              ticketCategoryName: tariff.name,
              unitPriceCents: tariff.unitPriceCents,
              quantity: quantity,
              availableCount: tariff.availableCount,
              eventCapacityTotal: event.capacityTotal,
            ),
          );

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '$quantity billet(s) ajouté(s) '
            'au panier.',
          ),
          action: SnackBarAction(
            label: 'Voir',
            onPressed: _openCart,
          ),
        ),
      );
    } on FanCartValidationException catch (error) {
      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.message),
        ),
      );
    }
  }

  Future<void> _selectTickets(
    FanCatalogEvent event,
  ) async {
    if (widget.cartOwnerKey == null || !event.canPurchaseTickets) {
      return;
    }

    final hasAvailableTariff = event.ticketCategories.any(
      (tariff) => tariff.isAvailable,
    );

    if (!hasAvailableTariff) {
      return;
    }

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        return FanTicketSelectionSheet(
          event: event,
          onAdd: (tariff, quantity) async {
            Navigator.of(sheetContext).pop();

            await _addToCart(
              event,
              tariff,
              quantity,
            );
          },
        );
      },
    );
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
    final scheme = Theme.of(context).colorScheme;
    final status = event.status.toUpperCase();

    final color = switch (status) {
      'PUBLISHED' => const Color(0xFF0B7A56),
      'POSTPONED' => const Color(0xFF8A5A02),
      'CANCELLED' => scheme.error,
      'SUSPENDED' => scheme.error,
      _ => scheme.onSurfaceVariant,
    };

    return Container(
      constraints: const BoxConstraints(maxWidth: 94),
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Text(
        event.statusLabel,
        key: ValueKey<String>('fan-event-status-${event.id}'),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        textAlign: TextAlign.center,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w800,
            ),
      ),
    );
  }

  Widget _eventImageFallback(
    FanCatalogEvent event,
  ) {
    return Container(
      key: ValueKey<String>(
        'fan-event-image-fallback-${event.id}',
      ),
      height: 132,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Icon(
        Icons.event_outlined,
        size: 56,
      ),
    );
  }

  Widget _eventImage(
    FanCatalogEvent event,
  ) {
    final imageUrl = event.imageUrl?.trim() ?? '';

    if (imageUrl.isEmpty) {
      return _eventImageFallback(event);
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(14),
      child: Image.network(
        imageUrl,
        key: ValueKey<String>(
          'fan-event-image-${event.id}',
        ),
        height: 132,
        width: double.infinity,
        fit: BoxFit.cover,
        errorBuilder: (
          context,
          error,
          stackTrace,
        ) {
          return _eventImageFallback(event);
        },
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
            _eventImage(event),
            const SizedBox(height: 16),
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
            Row(
              children: <Widget>[
                const Icon(
                  Icons.sell_outlined,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    event.ticketingLabel,
                    key: ValueKey<String>(
                      'fan-event-price-${event.id}',
                    ),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
              ],
            ),
            if (event.canPurchaseTickets && widget.cartOwnerKey != null) ...[
              const SizedBox(height: 16),
              FilledButton.icon(
                key: ValueKey<String>(
                  'fan-event-buy-${event.id}',
                ),
                onPressed: () {
                  _selectTickets(event);
                },
                icon: const Icon(
                  Icons.add_shopping_cart,
                ),
                label: const Text(
                  'Choisir mes billets',
                ),
              ),
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

    final sourceEvents = (snapshot.data ?? const <FanCatalogEvent>[])
        .where(
          (event) => event.status.toUpperCase() != 'ARCHIVED',
        )
        .toList(growable: false);

    if (sourceEvents.isEmpty) {
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

    final events = FanCatalogFilters.apply(
      sourceEvents,
      venue: _venueFilter,
      availability: _availabilityFilter,
      time: _timeFilter,
      now: _currentTime(),
    );

    final noResult = events.isEmpty;

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
        itemCount: 1 + (noResult ? 1 : events.length),
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (_, index) {
          if (index == 0) {
            return _filtersPanel(
              sourceEvents,
              events.length,
            );
          }

          if (noResult) {
            return const Padding(
              padding: EdgeInsets.symmetric(
                vertical: 32,
              ),
              child: Text(
                'Aucun événement ne correspond '
                'aux filtres sélectionnés.',
                textAlign: TextAlign.center,
              ),
            );
          }

          return _eventCard(
            events[index - 1],
          );
        },
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
                    _resetFilters();
                  });
                },
              ),
        actions: <Widget>[
          if (widget.cartOwnerKey != null)
            IconButton(
              key: const ValueKey<String>(
                'fan-cart-open',
              ),
              tooltip: 'Mon panier',
              icon: const Icon(
                Icons.shopping_cart_outlined,
              ),
              onPressed: _openCart,
            ),
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
