# syntax=docker/dockerfile:1

# Multi-stage : image finale < 400 Mo (cible §5.2), pas d'outils de build dedans.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Version de pip corrigée pour les vulnérabilités détectées par pip-audit.
RUN python -m pip install --no-cache-dir --upgrade "pip==26.2.1"

WORKDIR /app


# --- Stage build : compile les dépendances nécessitant un compilateur ---

FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/

RUN python -m pip install --no-cache-dir --user -r requirements/dev.txt


# --- Stage dev : image utilisée par docker-compose.yml (hot-reload, deps de test) ---

FROM base AS dev

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

COPY . .

COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000 8001

ENTRYPOINT ["/app/docker/entrypoint.sh"]

CMD ["api"]


# --- Stage prod : dépendances de production uniquement, utilisateur non-root ---

FROM base AS prod-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/

RUN python -m pip install --no-cache-dir --prefix=/install -r requirements/prod.txt


FROM base AS prod

RUN groupadd -r fanid \
    && useradd -r -g fanid fanid

COPY --from=prod-builder /install /usr/local

COPY --chown=fanid:fanid . .

RUN chmod +x /app/docker/entrypoint.sh

USER fanid

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]

CMD ["api"]