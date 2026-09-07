import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../data/fan_tickets_remote_data_source.dart';
import '../../domain/fan_ticket.dart';

final fanTicketsProvider = FutureProvider.autoDispose<List<FanTicket>>(
  (ref) {
    final session = ref.watch(authControllerProvider).valueOrNull;

    if (session == null || session.access.trim().isEmpty) {
      throw const AuthFailure();
    }

    final dio = ref.watch(dioClientProvider).dio;
    return FanTicketsRemoteDataSource(dio).fetchTickets(
      accessToken: session.access,
    );
  },
);
