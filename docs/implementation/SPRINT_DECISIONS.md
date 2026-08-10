# SPRINT 0 — Décisions locales et écarts documentés

Conformément au master prompt §69/§70, ce document trace les décisions
prises sans remonter à l'utilisateur (non architecturales, ou résolues
sans ambiguïté par la hiérarchie des sources §3), et les écarts assumés.

## D-01 — Redis : instance unique, pas 3 instances isolées

**Contexte** : un précédent audit d'environnement (hors du périmètre de ce
Sprint, produit dans une session antérieure) recommandait 3 instances Redis
isolées (cache/broker/sécurité). Source B §2.1/§7.1 énumère explicitement
**8 services** pour `docker-compose.yml`, et le C4 conteneurs de Source A
(§1.4.2) ne montre qu'**un seul** conteneur Redis logique (« cache ·
verrous · sessions · channel layer · broker »).

**Résolution** : Source A/B sont les seules sources de vérité pour ce
Sprint (hiérarchie §3 : "décision explicite du document d'architecture"
prime sur tout artefact hors-source). Un seul service `redis`, partitionné
par numéro de DB logique (0=cache, 1=channel layer, 2=verrous, 3=broker
Celery, 4=résultats Celery — voir `.env.example`). Pas de question
bloquante : Source B est explicite et non ambiguë sur le compte de 8
services.

## D-02 — Séquence `outbox_event.sequence` : `BigIntegerField` + séquence SQL manuelle

Django interdit un second `AutoField`/`BigAutoField` non-PK sur un modèle
(erreur système `fields.E100`). La colonne `sequence` (bigserial, ordre
global d'insertion — Source B §3.1) est donc un `BigIntegerField(unique=True)`
côté modèle, avec la vraie séquence PostgreSQL (`CREATE SEQUENCE ... OWNED
BY`, `DEFAULT nextval(...)`) posée par `RunSQL` dans la migration. Décision
locale (§5 master prompt), aucun impact sur le contrat d'API ni sur la
sémantique métier.

## D-03 — `django_celery_beat` installé mais planification statique (code) au Sprint 0

`django_celery_beat` reste dans `INSTALLED_APPS` (admin futur pour une
planification pilotable en base aux sprints métier), mais
`CELERY_BEAT_SCHEDULE` (code, `config/settings/base.py`) pilote les deux
tâches du Sprint 0 (relais Outbox 2s, purges quotidiennes) — la
`DatabaseScheduler` aurait exigé un seed de données au premier démarrage
pour un bénéfice nul à ce stade (YAGNI, §5 master prompt).

## D-04 — Migrations écrites à la main, pas générées par `makemigrations`

**Limitation d'environnement** (voir `SPRINT_TEST_REPORT.md`) : ce sandbox
n'a aucun accès réseau à PyPI, donc Django n'a pas pu être installé pour
exécuter `makemigrations`. Les deux migrations initiales
(`apps/identity/migrations/0001_initial.py`,
`apps/core/migrations/0001_infrastructure.py`) ont été écrites à la main en
reproduisant fidèlement la sortie attendue de `makemigrations` pour les
modèles définis. **Action requise avant le premier merge** : exécuter
`python manage.py makemigrations --check --dry-run` sur une machine avec
Django installé (c'est une porte bloquante de `ci-backend.yml`) et
corriger tout écart détecté.

## D-05 — Échantillonnage de traces adaptatif (conservation des erreurs) non implémenté

Source B §5.3 demande un échantillonnage 20% en production « avec
conservation systématique des traces en erreur ». Cela nécessite un
exportateur *tail-based sampling* (décision prise après coup, au niveau du
collecteur ou d'un service dédié), non trivial à poser au Sprint 0 sans
service supplémentaire. **Dette technique assumée et documentée** (voir
Source B §7.3 « Dette technique assumée » — cohérent avec l'esprit du
tableau existant) : le Sprint 0 livre un échantillonnage head-based fixe
(`ParentBased(TraceIdRatioBased(...))`, `tracing.py`) ; le raffinement
tail-based est différé, sans date fixée, à documenter comme risque ouvert
si le Sprint 5 ne le traite pas.

## D-06 — Pas de service `mailpit`/SMTP local au Sprint 0

Un précédent audit d'environnement (même remarque que D-01) ajoutait
`mailpit`. `notifying` est une coquille vide au Sprint 0 (§80 master
prompt : aucune notification métier) et Source B compte exactement 8
services — ajouter un 9ᵉ service pour un besoin qui n'existe pas encore
serait du scope creep (§81 master prompt). Réintroduit quand `notifying`
aura un envoi réel à tester (Sprint 3/4).

## D-07 — Correction post-bilan (P2.2) : `InProcessPublisher` renommé `UnimplementedEventPublisher`

**Constat du bilan (note 72/100)** : `apps/core/adapters/events.py` définissait
une classe `InProcessPublisher` — nom qui laisse entendre une implémentation
V1 fonctionnelle du port `EventPublisher` — dont les deux méthodes ne
faisaient que lever `NotImplementedError`. Une classe concrète qui prétend
implémenter un port mais échoue systématiquement est un piège : un
développeur pressé qui la voit dans `adapters/events.py` peut raisonnablement
supposer qu'elle fonctionne.

**Résolution** : renommée `UnimplementedEventPublisher`, avec un docstring qui
explique explicitement (a) pourquoi aucune implémentation directe de ce port
n'existe au Sprint 0 — la voie normale est
`apps.core.outbox.publisher.publish_event()` + le registre de consommateurs
in-process de `outbox/relay.py`, qui ne passe pas par ce port — et (b) que
`RecordingPublisher` (déjà présent, inchangé) reste le double de test concret
du port. Aucun appelant existant dans le code (vérifié par recherche globale) :
renommage sans impact fonctionnel. Décision locale non architecturale (§69/§70
master prompt) : le port `EventPublisher` lui-même, sa place dans
`core/interfaces/`, et le principe qu'une V2 (SQS/Kafka) le bascule sans
refonte restent inchangés (Source A §1.1.2 B, Source B §2.3).
