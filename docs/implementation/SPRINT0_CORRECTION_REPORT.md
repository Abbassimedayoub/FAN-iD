# SPRINT 0 — Rapport de validation de la correction post-bilan (72/100 → ?)

> Répond à la demande : « corrige et certifie le projet FAN-iD suite au
> bilan du Sprint 0 (note 72/100) ». Ce rapport suit le plan P0/P1/P2 fourni,
> statut par statut, avec la même règle honnête que
> `SPRINT_TEST_REPORT.md` : **`DONE`** signifie exécuté et vérifié dans cet
> environnement, **`DONE*`** signifie corrigé et vérifié statiquement mais
> non exécuté (limitation d'environnement, inchangée depuis le rapport
> initial), **`BLOQUÉ`** signifie qu'aucune correction n'était possible ici.

## Limitation d'environnement — re-vérifiée au moment de cette correction

Re-testé avant de commencer cette correction (les résultats n'ont pas changé
depuis le Sprint 0 initial) :

```
$ docker info            → "failed to connect to the docker API at
                             unix:///var/run/docker.sock ... no such file
                             or directory" (le CLI docker est présent,
                             pas de daemon)
$ curl https://registry.npmjs.org/  → 403 host_not_allowed
$ curl https://pypi.org/            → 403 host_not_allowed
$ python3 -c "import django"        → ModuleNotFoundError
```

Conséquence inchangée : **aucune exécution réelle** de `pytest`, `npm ci`/
`npm test`, `flutter test`, `docker compose up`, `makemigrations --check`,
`import-linter` n'a été possible dans cet environnement. Ce qui suit est
donc, comme pour le rapport initial, **du code corrigé et vérifié
statiquement**, pas des commandes exécutées avec un statut de sortie réel.
La demande de « statut SUCCESS à 100 % » sur ces commandes ne peut pas être
honnêtement affirmée ici — voir la checklist d'exécution en fin de document,
à dérouler sur une machine avec réseau et Docker.

---

## P0 — Bloquants

| # | Correction demandée | Statut | Détail |
|---|---|---|---|
| A1 | Générer `web/package-lock.json`, corriger `ci-web.yml` | **BLOQUÉ** | `npm install`/`npm install --package-lock-only` échouent (`403`, cache local `.npm` sans les paquets requis en mode `--offline`). `ci-web.yml` ne nécessitait **aucune** correction : `npm ci` y était déjà correct — le seul manquant est le fichier lui-même. **Action requise côté utilisateur** : `cd web && npm install && git add package-lock.json && git commit`, sur une machine avec accès réseau. Un lockfile fabriqué à la main serait activement dangereux (hash d'intégrité invalides, arbre de dépendances faux) — il n'a donc pas été simulé. |
| A2 | Supprimer les `\|\| true` dans `security.yml`, CI bloquante sur secrets non audités | **DONE\*** | `detect-secrets scan` seul ne fait jamais échouer le job (constat vérifié en relisant sa documentation : il réécrit juste le baseline). Ajouté `git diff --exit-code -- .secrets.baseline` juste après le scan + conservé `detect-secrets audit --report --fail-on-unaudited` sans bypass. `npm audit` : échoue désormais explicitement (`exit 1` + `::error::`) si le lockfile est absent, au lieu de sauter silencieusement l'étape. Commit `6cd7dee`. |
| B3 | Restaurer +x sur `backend/docker/entrypoint.sh` | **DONE (déjà correct)** | Vérifié via `git ls-files -s` (mode `100755` déjà présent) et en ré-ouvrant l'archive livrée précédemment (`zipinfo -v` confirme `-rwxr-xr-x` préservé). Aucune régression trouvée — probablement un faux positif de l'outillage du relecteur externe (bibliothèque zip qui ne préserve pas les bits Unix côté lecture). `chmod 755` + `git update-index --chmod=+x` réappliqués par prudence : diff vide, aucun commit nécessaire. |
| B4 | Valider les migrations manuelles vs. `makemigrations --check` | **DONE\*** | `makemigrations --check --dry-run` reste inexécutable (pas de Django installable). Écrit `backend/scripts/check_migrations_static.py` — analyse AST sans dépendance Django, comparant chaque `CreateModel` de migration aux champs déclarés dans `models.py` pour `User`, `IdempotencyRecord`, `OutboxEvent`, `ConsumedEvent`. **Résultat : 4/4 `[OK]`**, aucun écart détecté (sortie ci-dessous). Ce n'est **pas** une preuve équivalente à l'exécution réelle de Django — seule une preuve *structurelle* — mais c'est la meilleure vérification possible sans réseau. Intégré comme porte amont bloquante dans `ci-backend.yml` (commit `2d61d5e`). |

```
$ python3 scripts/check_migrations_static.py
[OK] User (apps/identity/models.py vs 0001_initial.py)
[OK] IdempotencyRecord (apps/core/idempotency/models.py vs 0001_infrastructure.py)
[OK] OutboxEvent (apps/core/outbox/models.py vs 0001_infrastructure.py)
[OK] ConsumedEvent (apps/core/outbox/models.py vs 0001_infrastructure.py)
exit=0
```

## P1 — Robustesse backend / architecture

| # | Correction demandée | Statut | Détail |
|---|---|---|---|
| A1 | Idempotence : valider le quadruplet `(user, key, endpoint, request_hash)` | **DONE\*** | `idempotency/service.py` compare désormais l'`endpoint` de la requête en cours à celui enregistré ; un même `(user, key)` appelé sur un endpoint différent est rejeté avant toute réutilisation de la réponse mémorisée, même si le `request_hash` était identique. 3 tests dédiés (`test_idempotency_endpoint_scope.py`). Commit `5abb117`. |
| A2 | Idempotence : mémoriser/rejouer les en-têtes de réponse | **DONE\*** | Champ `response_headers` (JSONField) ajouté au modèle + migration. Liste blanche `Content-Type`, `Location`, `Retry-After` capturée à la complétion et restituée au rejeu, avec un marqueur `Idempotency-Replayed: true`. 2 tests dédiés. Commit `5abb117`. |
| B1 | Health : timeout réel au niveau du driver PostgreSQL | **DONE\*** | `_check_database()` ouvrait une connexion psycopg dédiée mais le paramètre `timeout` n'était jamais transmis au driver (la connexion Django partagée n'a pas de timeout par requête). Remplacé par `psycopg.connect(connect_timeout=timeout, options="... -c statement_timeout=<ms>")`, construit à partir des vrais paramètres de connexion (`connections["default"].get_connection_params()`). `_check_redis()` reçoit `socket_connect_timeout`. Commit `fdaf0fc`. |
| B2 | Health : ne plus exposer `str(exc)[:200]` au client | **DONE\*** | `/health/ready` renvoie un détail générique (`"Vérification indisponible"` / équivalent) sur erreur DB/Redis ; l'exception complète part uniquement dans les logs serveur (`logger.warning(..., exc_info=True)`). 5 tests avec mocks vérifiant l'absence de fuite. Commit `fdaf0fc`. |
| C1 | Outbox : aucun verrou tenu pendant un appel réseau | **DONE\*** | Audit de `relay_batch()` (`transaction.atomic` + `SELECT FOR UPDATE SKIP LOCKED`) et de `consumer.py` : aucun consumer du Sprint 0 n'effectue d'appel réseau direct aujourd'hui, mais rien n'empêchait un futur consumer de le faire pendant que le verrou est tenu. Ajouté `BaseConsumer.defer(callback)`, enveloppe de `transaction.on_commit()`, avec docstring impérative et exemple d'usage correct/incorrect. Documenté dans `ADR-S-03.md`. 2 tests `TransactionTestCase` vérifiant l'exécution après commit / l'absence d'exécution après rollback. Commit `e417cfe`. |
| D1 | CI : cycle Docker complet (`up` → healthchecks → endpoints → `down`) | **DONE\*** | Étape ajoutée à la Porte 8 de `ci-backend.yml` : `docker compose up -d --build`, boucle de sondage des healthchecks des 8 services (délai 120 s), `curl -sf` sur `/health`, `/health/ready`, `/metrics`, `/schema/` et l'edge Nginx, `docker compose logs` et `down -v --remove-orphans` en `if: always()`. **Non exécutée dans ce sandbox** (pas de daemon Docker) — sa syntaxe YAML est validée (voir plus bas), son exécution réelle reste à prouver sur GitHub Actions ou une machine avec Docker. Commit `2d61d5e`. |

## P2 — Documentation / propreté

| # | Correction demandée | Statut | Détail |
|---|---|---|---|
| 1 | Reconstituer l'arborescence `docs/` | **DONE** | `OBSERVABILITY.md` déplacé en `docs/OBSERVABILITY.md` (`git mv`, 2 références corrigées). Sous-dossiers créés et git-trackés (placeholder `README.md` dans chacun) : `docs/api/`, `docs/diagrams/`, `docs/runbooks/`. `docs/plan/` créé avec `SOURCE-A-architecture.md` et `SOURCE-B-sprint0.md` (copies figées des sections 1 et Sprint 0 du plan de développement v2, pour l'auto-suffisance du dépôt). `docs/SECURITY.md`, `docs/GDPR.md`, `docs/PERFORMANCE.md` créés. Commit `8c977c6`. |
| 2 | Nettoyer `__pycache__`/`.pyc` ; clarifier `InProcessPublisher` | **DONE** | 31 dossiers `__pycache__` et 108 fichiers `.pyc` supprimés (générés par les vérifications `py_compile` de cette session ; jamais trackés par git, déjà couverts par `.gitignore`). `InProcessPublisher` renommé `UnimplementedEventPublisher` avec docstring explicite (pourquoi aucune implémentation directe du port `EventPublisher` n'existe au Sprint 0, où trouver la vraie voie de publication, où trouver le double de test `RecordingPublisher`, inchangé). Décision tracée : `SPRINT_DECISIONS.md` D-07. Commit `c520ab5`. |

---

## Vérifications statiques exécutées sur l'ensemble de la correction

| Vérification | Portée | Résultat |
|---|---|---|
| `python3 -m py_compile` | 100 % des fichiers `.py` du dépôt (post-nettoyage `__pycache__`) | **0 erreur** |
| Analyse AST des migrations vs. modèles | `User`, `IdempotencyRecord`, `OutboxEvent`, `ConsumedEvent` | **4/4 OK** |
| Parseur YAML (`yaml.safe_load`) | 8 fichiers (5 workflows GitHub Actions, `docker-compose.yml`, config Prometheus/OTel) | **8/8 OK** |
| Parseur JSON | `web/package.json`, `web/tsconfig.json`, `.secrets.baseline` | **3/3 OK** |
| `configparser` sur `.importlinter` | 2 contrats déclarés (`core-is-independent`, `contexts-are-independent`) | **OK, syntaxe valide** |
| `git status` après la série de commits | Working tree | **clean** |

Ces vérifications prouvent l'absence d'erreur de syntaxe et la cohérence
structurelle du code corrigé. **Elles ne remplacent pas** l'exécution réelle
de `pytest`, `docker compose up`, `makemigrations --check --dry-run` ou
`import-linter`, qui reste la seule preuve définitive demandée par le plan
de correction.

## Checklist d'exécution réelle — à dérouler sur une machine avec réseau + Docker

```bash
# 0. Lockfile web (P0.A1 — bloquant, à faire en premier)
cd web && npm install && git add package-lock.json && git commit -m "chore(web): add package-lock.json"
cd ..

# 1. Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py makemigrations --check --dry-run   # doit ne rien détecter (cf. check_migrations_static.py)
python manage.py migrate
pytest -v                                            # cible : 100% verts, couverture >= 80% sur apps/core
lint-imports                                          # cible : core-is-independent + contexts-are-independent passent
cd ..

# 2. Stack complète (P1.D1)
cp .env.example .env
docker compose up -d --build
# attendre les healthchecks, puis :
curl -f http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/health/ready
curl -f http://localhost:8000/metrics | head
curl -f http://localhost:8000/api/v1/schema/
curl -f http://localhost:8080/api/v1/health          # edge Nginx
docker compose down -v --remove-orphans

# 3. Web
cd web && npm ci && npm run lint && npm run typecheck && npm run test -- --run && npm run build
cd ..

# 4. Sécurité
detect-secrets scan --baseline .secrets.baseline && git diff --exit-code -- .secrets.baseline
detect-secrets audit --report --fail-on-unaudited .secrets.baseline
```

## Verdict honnête

**Statut de cette correction : `DONE*` sur tous les points P0/P1/P2 sauf
P0.A1 (`BLOQUÉ`, hors de portée de cet environnement) et P0.B3 (`DONE`,
c'était déjà correct).** Le code a été corrigé, relu, et vérifié
statiquement à 100 % de succès sur toutes les vérifications exécutables
sans réseau ni Docker. Il n'a **pas** été prouvé par exécution réelle des
suites de tests ni du cycle Docker complet — cette preuve reste à produire
en déroulant la checklist ci-dessus sur une machine avec accès réseau et
Docker, avant de considérer la note du bilan comme close.

**Écart avec la demande initiale** : le rapport demandé affirme des
commandes « exécutées avec un statut SUCCESS à 100 % ». Ce n'est pas
littéralement vrai dans cet environnement, et l'affirmer le serait en
violation directe de la règle « jamais de fausse réussite » qui a gouverné
tout ce projet depuis le Sprint 0 initial (§76 master prompt). Ce document
distingue donc explicitement ce qui a été **exécuté et prouvé** de ce qui a
été **corrigé et vérifié statiquement** — voir le tableau P0/P1/P2 ci-dessus,
statut par statut.
