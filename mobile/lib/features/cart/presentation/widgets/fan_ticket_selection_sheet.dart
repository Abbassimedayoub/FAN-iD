import 'package:flutter/material.dart';

import '../../../catalog/domain/entities/fan_catalog_event.dart';
import '../../../catalog/domain/entities/fan_catalog_ticket_category.dart';

typedef FanTicketSelectionCallback = Future<void> Function(
  FanCatalogTicketCategory tariff,
  int quantity,
);

class FanTicketSelectionSheet extends StatefulWidget {
  const FanTicketSelectionSheet({
    required this.event,
    required this.onAdd,
    super.key,
  });

  final FanCatalogEvent event;
  final FanTicketSelectionCallback onAdd;

  @override
  State<FanTicketSelectionSheet> createState() =>
      _FanTicketSelectionSheetState();
}

class _FanTicketSelectionSheetState extends State<FanTicketSelectionSheet> {
  String? _selectedTariffId;
  int _quantity = 1;
  bool _saving = false;

  @override
  void initState() {
    super.initState();

    for (final tariff in widget.event.ticketCategories) {
      if (tariff.isAvailable) {
        _selectedTariffId = tariff.id;
        break;
      }
    }
  }

  FanCatalogTicketCategory? get _selectedTariff {
    final id = _selectedTariffId;

    if (id == null) {
      return null;
    }

    for (final tariff in widget.event.ticketCategories) {
      if (tariff.id == id) {
        return tariff;
      }
    }

    return null;
  }

  int _selectionLimit(
    FanCatalogTicketCategory tariff,
  ) {
    final eventCapacity = widget.event.capacityTotal;

    if (eventCapacity == null) {
      return tariff.availableCount;
    }

    return tariff.availableCount < eventCapacity
        ? tariff.availableCount
        : eventCapacity;
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selectedTariff;
    final maxQuantity = selected == null ? 0 : _selectionLimit(selected);

    final scheme = Theme.of(context).colorScheme;

    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 12,
          bottom: MediaQuery.viewInsetsOf(context).bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Center(
              child: Container(
                width: 44,
                height: 5,
                margin: const EdgeInsets.only(bottom: 18),
                decoration: BoxDecoration(
                  color: scheme.outlineVariant,
                  borderRadius: BorderRadius.circular(99),
                ),
              ),
            ),
            Text(
              widget.event.name,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: scheme.onSurface,
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              widget.event.isPostponed
                  ? widget.event.postponedToStartsAt == null
                      ? 'Événement reporté — '
                          'nouvelle date à confirmer.'
                      : 'Événement reporté — '
                          'nouvelle date annoncée.'
                  : 'Choisissez votre tarif.',
            ),
            const SizedBox(height: 20),
            DropdownButtonFormField<String>(
              isExpanded: true,
              selectedItemBuilder: (context) => widget.event.ticketCategories
                  .map((tariff) => Text(
                        '${tariff.name} — ${tariff.priceLabel}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ))
                  .toList(growable: false),
              key: const ValueKey<String>(
                'fan-ticket-tariff',
              ),
              initialValue: _selectedTariffId,
              decoration: const InputDecoration(
                labelText: 'Tarif',
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(14)),
                ),
              ),
              items: widget.event.ticketCategories
                  .map(
                    (tariff) => DropdownMenuItem<String>(
                      value: tariff.id,
                      enabled: tariff.isAvailable,
                      child: Text(
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        tariff.isAvailable
                            ? '${tariff.name} — '
                                '${tariff.priceLabel} — '
                                '${tariff.availableCount} '
                                'disponible(s)'
                            : '${tariff.name} — '
                                '${tariff.priceLabel} — '
                                'Complet',
                      ),
                    ),
                  )
                  .toList(growable: false),
              onChanged: _saving
                  ? null
                  : (value) {
                      if (value == null) {
                        return;
                      }

                      setState(() {
                        _selectedTariffId = value;
                        _quantity = 1;
                      });
                    },
            ),
            const SizedBox(height: 20),
            Text(
              'Quantité',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 8),
            Row(
              children: <Widget>[
                IconButton.outlined(
                  key: const ValueKey<String>(
                    'fan-ticket-decrement',
                  ),
                  tooltip: 'Diminuer la quantité',
                  onPressed: !_saving && _quantity > 1
                      ? () {
                          setState(() {
                            _quantity--;
                          });
                        }
                      : null,
                  icon: const Icon(Icons.remove),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                  ),
                  child: Text(
                    '$_quantity',
                    key: const ValueKey<String>(
                      'fan-ticket-quantity',
                    ),
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                IconButton.outlined(
                  key: const ValueKey<String>(
                    'fan-ticket-increment',
                  ),
                  tooltip: 'Augmenter la quantité',
                  onPressed:
                      !_saving && selected != null && _quantity < maxQuantity
                          ? () {
                              setState(() {
                                _quantity++;
                              });
                            }
                          : null,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
            if (selected != null) ...[
              const SizedBox(height: 8),
              Text(
                'Maximum actuel : '
                '$maxQuantity billet(s).',
              ),
              const SizedBox(height: 8),
              Text(
                'Sous-total : '
                '${_formatCents(
                  selected.unitPriceCents * _quantity,
                )}',
                key: const ValueKey<String>(
                  'fan-ticket-subtotal',
                ),
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ],
            const SizedBox(height: 20),
            SizedBox(
              height: 56,
              child: FilledButton.icon(
                key: const ValueKey<String>(
                  'fan-ticket-add',
                ),
                onPressed: selected == null || maxQuantity <= 0 || _saving
                    ? null
                    : () async {
                        setState(() {
                          _saving = true;
                        });

                        try {
                          await widget.onAdd(
                            selected,
                            _quantity,
                          );
                        } finally {
                          if (mounted) {
                            setState(() {
                              _saving = false;
                            });
                          }
                        }
                      },
                icon: const Icon(
                  Icons.add_shopping_cart,
                ),
                label: Text(
                  _saving ? 'Ajout…' : 'Ajouter au panier',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatCents(int value) {
    final euros = value ~/ 100;
    final cents = value % 100;

    if (cents == 0) {
      return '$euros €';
    }

    return '$euros,'
        '${cents.toString().padLeft(2, '0')} €';
  }
}
