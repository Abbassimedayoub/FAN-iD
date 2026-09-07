import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth/presentation/providers/auth_providers.dart';

import '../../../../core/network/dio_client.dart';
import '../../data/fan_tickets_remote_data_source.dart';
import '../../domain/fan_ticket.dart';

final fanTicketsProvider = FutureProvider.autoDispose<List<FanTicket>>(
  (ref) {
    final dio = ref.watch(dioClientProvider).dio;

    return FanTicketsRemoteDataSource(dio).fetchTickets();
  },
);
