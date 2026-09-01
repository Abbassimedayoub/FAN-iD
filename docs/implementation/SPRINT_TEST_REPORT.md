# SPRINT 0 — Rapport de test

## Limitation d'environnement (à lire en premier)

L'environnement dans lequel ce Sprint 0 a été implémenté est un sandbox
cloud **sans accès réseau sortant vers PyPI, npm, ou Docker Hub**, et
**sans daemon Docker actif** (vérifié : `curl https://pypi.org` → `403
host_not_allowed` ; `curl https://registry.npmjs.org` → `403
host_not_allowed` ; `docker pull hello-world` → `no such file or
directory: /var/run/docker.sock`).

Conséquence directe : **aucune des commandes suivantes n'a pu être
exécutée** dans cet environnement :

- `pip install -r requirements/*.txt` (Django, DRF, Celery, pytest... non installables)
- `python manage.py migrate` / `makemigrations`
- `pytest` (aucun test réel exécuté)
- `docker compose up` / `docker build`
- `npm install` / `npm run build` / `npm run test` / `tsc --noEmit`
- `flutter pub get` / `flutter test` / `flutter analyze`
- `lint-imports`, `black`, `flake8`, `mypy`, `bandit`, `pip-audit`, `detect-secrets`

Ceci a été signalé à l'utilisateur **avant** de poursuivre l'implémentation
(règle §76 master prompt : jamais de fausse réussite), et non découvert a
posteriori.

## Ce qui A été fait pour compenser, dans la limite du possible

1. **Vérification syntaxique complète** — `python3.12 -m py_compile` sur
   l'intégralité des fichiers `.py` de `backend/` (hors `.venv`) :
   **succès, 0 erreur**. Preuve que le code est syntaxiquement valide en
   Python 3.12, pas que la logique est correcte à l'exécution.
2. **Relecture ligne à ligne** de chaque fichier au moment de l'écriture,
   contre Source A (architecture) et Source B (Sprint 0), avec citation
   explicite des sections dans les commentaires du code lui-même.
3. **Migrations écrites à la main** en reproduisant fidèlement le format
   de sortie de `makemigrations` (voir `SPRINT_DECISIONS.md` D-04) — un
   risque résiduel existe que cette reproduction manuelle contienne une
   erreur qu'un `makemigrations --check --dry-run` réel détecterait
   immédiatement.
4. **`docker compose config`** n'a pas pu être exécuté (pas de binaire
   Docker fonctionnel), donc la validité YAML du `docker-compose.yml` n'a
   été vérifiée que par relecture manuelle, pas par le parseur réel.

## Ce qui reste à faire, sur une machine avec accès réseau + Docker

```bash
# 1. Backend — installation et vérification complète
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py makemigrations --check --dry-run   # DOIT ne rien détecter — sinon corriger 0001_infrastructure.py / identity 0001_initial.py à la main
python manage.py migrate
pytest -v                                            # cible : 100% verts, couverture >= 80% sur apps/core
lint-imports                                          # cible : core-is-independent + contexts-are-independent passent
black --check . && isort --check-only . && flake8 .
mypy apps/core
bandit -r apps config -ll
pip-audit -r requirements/prod.txt

# 2. Stack complète
cd ..
cp .env.example .env
docker compose config                                 # valide la syntaxe réelle du compose
docker compose up --build
curl -f http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/health/ready
curl -f http://localhost:8000/metrics | head

# 3. Web
cd web && cp .env.example .env && npm install
npm run lint && npm run typecheck && npm run test -- --run && npm run build

# 4. Mobile
cd ../mobile && flutter pub get
flutter analyze && flutter test
```

## Verdict honnête

**Le Sprint 0 n'est PAS prouvé DONE au sens du master prompt §76-§84** —
le code est complet et cohérent avec Source A/B, mais aucune preuve
d'exécution n'a pu être produite dans cet environnement. Statut réel :
**DONE\* (code écrit, non exécuté)** — voir `SPRINT_STATUS.md`.

**Prochaine étape recommandée** : exécuter la séquence ci-dessus sur une
machine avec accès réseau et Docker (poste de développement local ou CI
GitHub Actions réelle), corriger tout écart révélé par
`makemigrations --check` ou `pytest` (le risque le plus probable
concerne les migrations écrites à la main, D-04), puis mettre à jour ce
rapport avec les résultats réels avant de considérer le Sprint 0 terminé.
