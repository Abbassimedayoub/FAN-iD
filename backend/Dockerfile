# syntax=docker/dockerfile:1

# Multi-stage build: keep the final image below the size target and exclude build tools.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Pin a patched pip version for vulnerabilities reported by pip-audit.
RUN python -m pip install --no-cache-dir --upgrade "pip==26.2.1"

WORKDIR /app


# --- Build stage: compile dependencies that require a compiler ---

FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/

RUN python -m pip install --no-cache-dir --user -r requirements/dev.txt


# --- Development stage: used by docker-compose.yml for hot reload and test dependencies ---

FROM base AS dev

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

COPY . .

COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000 8001

ENTRYPOINT ["/app/docker/entrypoint.sh"]

CMD ["api"]


# --- Production stage: production-only dependencies and a non-root user ---

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
