# System and workflow diagrams

These diagrams describe the main components and business flows of FAN iD. They summarize application behavior rather than every internal call.

## Application structure

```mermaid
flowchart TD
    Web["React web portal"] --> API["Django REST API"]
    Mobile["Flutter application"] --> API
    API --> DB[("PostgreSQL")]
    API --> Redis[("Redis-compatible service")]
    API --> Storage["Media storage adapter"]
    API --> Stripe["Stripe"]
    Stripe -->|"Signed webhooks"| API
    Beat["Celery beat"] --> Redis
    Redis --> Worker["Celery worker"]
    Worker --> DB
    Worker --> Stripe
    Worker --> Mail["Notifications"]
```

Local development uses Docker Compose. The hosted demonstration uses Cloudflare Pages for the web portal, Render for the backend and data services, and Cloudflare R2 for media. API and workers share server-side configuration.

## Purchase and ticket issuance

```mermaid
sequenceDiagram
    participant App as Mobile app
    participant API as Django API
    participant Stripe as Stripe
    participant DB as PostgreSQL
    App->>API: Reserve tickets
    API-->>App: Order identifier
    App->>API: Prepare payment
    API->>Stripe: Create or obtain payment session
    API-->>App: Payment session
    App->>Stripe: Confirm through PaymentSheet
    Stripe->>API: Signed payment_intent.succeeded
    API->>DB: Check reservation and consume hold
    API->>DB: Confirm order and issue tickets atomically
    App->>API: Read order and tickets
    API-->>App: Updated purchase state
```

Ticket issuance and order confirmation share a transaction. Payment received after reservation expiry needs reconciliation; it must not be treated as an automatically valid ticket purchase.

## Event cancellation and refund

```mermaid
sequenceDiagram
    participant Org as Organizer
    participant API as Django API
    participant Worker as Celery worker
    participant Stripe as Stripe
    Org->>API: Cancel event and request refunds
    API->>API: Save cancellation and outbox event
    API-->>Org: Cancellation accepted
    API-->>Worker: Outbox-driven refund task
    Worker->>Stripe: Request refund
    Stripe->>API: Signed refund.updated
    API->>API: Record refund outcome
    Org->>API: Read updated event state
```

Refunds may finish after the cancellation response. Check both the provider outcome and the application state.

## Admission validation

```mermaid
flowchart TD
    Scan["Scanner submits ticket QR"] --> Check["Server validates permissions and admission rules"]
    Check -->|"Rejected"| Deny["Return refusal"]
    Check -->|"Accepted"| Record["Record admission"]
    Record --> Result["Return successful scan"]
```

Ticket validity and duplicate-entry protection are enforced by the backend, not by the QR display alone.

## Related documents

- [Architecture](../adr/README.md)
- [API reference](../api/README.md)
- [Project README](../../README.md)
