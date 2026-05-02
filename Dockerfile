# syntax=docker/dockerfile:1.6
# ──────────────────────────────────────────────────────────────────────────────
# BaDzi-Bot — multi-stage image for bot / web / worker
# Base: python:3.11-slim-bookworm
# Domain: pyswisseph (C ext), Playwright Chromium (HTML→PNG cards), CJK fonts
# ──────────────────────────────────────────────────────────────────────────────

ARG PYTHON_VERSION=3.11
ARG PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG PLAYWRIGHT_BROWSERS_PATH
ENV PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH} \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY pyproject.toml ./

RUN pip install --upgrade pip setuptools wheel \
    && pip install .

RUN python -m playwright install --with-deps chromium

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG PLAYWRIGHT_BROWSERS_PATH
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder ${PLAYWRIGHT_BROWSERS_PATH} ${PLAYWRIGHT_BROWSERS_PATH}

RUN useradd --create-home --uid 1000 --shell /bin/bash app \
    && chown -R app:app ${PLAYWRIGHT_BROWSERS_PATH}

WORKDIR /app
COPY --chown=app:app . /app

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import bot.config" || exit 1
