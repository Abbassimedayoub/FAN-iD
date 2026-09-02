# FAN ID — MVP Development Board

## Board Tool

GitHub Projects is used as the project-management tool for FAN ID because it connects planning directly to repository issues, pull requests, commits, labels, CI checks and implementation evidence.

> Project board link: add the public/shareable GitHub Project URL before submission.

## Board Structure

The board uses the following workflow columns:

- **Backlog** — planned work that is not ready to start yet.
- **To Do** — prioritized work ready to begin next.
- **In Progress** — work currently being implemented.
- **In Review** — implementation completed and waiting for pull-request/self-review.
- **Testing** — implementation available and being validated against acceptance criteria.
- **Blocked** — work that cannot progress because of a dependency, technical problem or external constraint.
- **Done** — work fully completed according to the Definition of Done.

## Planning Fields

Each development card is managed with the following planning information:

- **Status**
- **Priority** — Must / Should / Could
- **Sprint**
- **Estimate** — story points
- **Area** — Backend, Frontend, Mobile, Database, API, Security, Testing, Deployment, Documentation or UI/UX
- **Deadline** — 16 September 2027
- **Assignee** — Abbassimedayoub
- **Labels** — technical and functional tags such as backend, frontend, mobile, database, API, security, testing, deployment, documentation, payment, ticketing, authentication, scanner, CI/CD and bug.

User-story traceability is kept directly in issue titles and descriptions through identifiers such as `US-01`, `US-02`, etc. Each user-story issue contains a `Related User Story` section and acceptance criteria.

## Sprints / Milestone Goals

### M1 — Identity & Access

Goal: deliver secure account access and identity workflows.

Includes registration, verification, authentication, device binding/recovery, organizer approval and transactional identity notifications.

### M2 — Event Catalog

Goal: allow organizers to manage events and fans to discover valid published events.

Includes event CRUD/archive behavior, ticket categories, capacity rules, publication, search, filtering, sorting and pagination.

### M3 — Purchase & Ticketing

Goal: complete the purchase-to-ticket lifecycle.

Includes Stripe payment confirmation, ticket issuance, My Tickets, dynamic QR credentials and account-to-account transfer.

### M4 — Access Control

Goal: validate tickets securely at event entry.

Includes scanner assignment, scan validation, APPROVED / REJECTED / CANNOT VERIFY outcomes, atomic ticket consumption and organizer attendance metrics.

### M5 — Quality & Deployment

Goal: make the MVP releasable, testable and documented.

Includes end-to-end tests, security hardening, CI/CD, production deployment, backups, recovery, documentation and bug triage.

## Card Structure

Development issues use action-oriented titles and contain:

- Description
- Related User Story
- Acceptance Criteria
- Assignee
- Priority
- Sprint
- Estimate
- Area
- Deadline
- Definition of Done

Large user stories may be represented as feature-level cards and then decomposed into smaller technical issues when implementation requires it.

## Definition of Done

A task is considered **Done** only when:

- the implementation is completed;
- all acceptance criteria are satisfied;
- relevant automated or manual tests pass;
- authorization and security requirements are reviewed when relevant;
- no secrets, temporary debug code or unsafe logging remain;
- documentation is updated when needed;
- CI checks pass when applicable;
- the associated pull request has been self-reviewed;
- the code is merged into the appropriate integration branch.

## Progress Tracking Method

Progress is tracked through the GitHub Project `Status` field. Cards move through:

`Backlog → To Do → In Progress → In Review → Testing → Done`

A task may move to `Blocked` at any point if it cannot progress.

The board is reviewed by sprint and priority. Must-have work is prioritized before Should/Could work. GitHub issues and pull requests provide traceability from planned work to implementation evidence.

## Risk and Blocker Tracking

Blocked tasks are moved to the **Blocked** column and should contain a comment or issue update using this structure:

```text
Blocker:
Reason:
Impact:
Required action:
Expected resolution:
```

Examples of possible blockers include unavailable external services, payment-provider configuration, deployment credentials, infrastructure limitations, unresolved dependencies or failing CI checks.

Confirmed defects are tracked as dedicated GitHub issues with the `bug` label and an explicit priority.

## Evidence for Submission

Submission evidence should include:

1. the shareable GitHub Project board link;
2. screenshots showing the board columns and populated cards;
3. screenshots or views showing Priority, Sprint, Estimate, Area, Deadline and Assignee fields;
4. representative issue details showing acceptance criteria and Definition of Done;
5. issue / pull-request history demonstrating movement from planning to implementation, review, testing and completion.

This document is the written explanation accompanying the FAN ID GitHub Project board.
