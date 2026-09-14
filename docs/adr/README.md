# Architecture

FAN iD is a ticketing and admission-control platform developed by Mohamed Ayoub Abbassi as an individual final project at Holberton School France.

## System structure

A React web portal serves administrators and organizers. A Flutter application serves fans and scanners. Both clients use a Django REST API backed by PostgreSQL.

The backend is a modular monolith: domains share a database and application deployment, while business responsibilities are separated into dedicated modules.

| Module | Responsibility |
| --- | --- |
| `identity` | Users, authentication, sessions and device binding |
| `organizing` | Organizer accounts and scanner management |
| `catalog` | Events, ticket categories, images and lifecycle actions |
| `ordering` | Reservations, stock holds and order confirmation |
| `payments` | Payment intents, Stripe webhooks and refunds |
| `ticketing` | Ticket issuance, transfers and dynamic QR codes |
| `access` | Admission sessions, scans and reporting |
| `notifying` | Transactional notifications |
| `core` | Shared infrastructure, outbox, idempotency and concurrency |
| `realtime` | Realtime integration boundary |

## Architectural decisions

| Decision | Reason and trade-off |
| --- | --- |
| Modular monolith | Keeps deployment manageable for a single-author project while separating business domains. Modules are not independently deployed services. |
| PostgreSQL as the transactional store | Keeps orders, reservations and tickets consistent. Stock changes require database concurrency controls. |
| Redis-compatible infrastructure | Supports caching, locks and Celery messaging. Availability matters beyond simple API reachability. |
| External-service adapters | Separates business rules from payment, storage and notification providers. Local adapters do not replace integration tests. |
| Transactional outbox | Records follow-up work with business changes. Consumers must tolerate retries and duplicate delivery. |
| Versioned updates | `ETag` and `If-Match` prevent stale writes. Clients must retain the current resource version. |

## Critical business flows

Payment confirmation consumes the reservation and issues tickets within one database transaction. If ticket issuance fails, order confirmation rolls back. The mobile payment screen alone cannot mark an order as paid.

Event cancellation with refunds requested publishes an outbox event. Background processing requests refunds, and signed Stripe events update refund outcomes. Cancellation acceptance and refund completion are separate states.

Admission decisions remain server-side. A QR image is not sufficient proof of a valid ticket; authorization, ticket state and admission rules must also pass.

## Runtime boundaries

Local development uses Docker Compose, PostgreSQL, Redis and local service adapters. The hosted environment uses Render, Cloudflare Pages, private R2 storage, SMTP and Stripe test mode.

Celery workers execute background tasks; Celery beat schedules recurring work. Django Channels is configured, but the ASGI WebSocket route list is currently empty.

Private credentials remain on the server. Frontend build variables contain only client-visible configuration. Public registration does not grant administrative privileges.

## Related documents

- [API reference](../api/README.md)
- [System and workflow diagrams](../diagrams/README.md)
- [Project README](../../README.md)
