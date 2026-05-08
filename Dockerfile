# syntax=docker/dockerfile:1.6
# ──────────────────────────────────────────────────────────────────────────────
# BaDzi-Bot — multi-stage image for bot / web / worker
# Base: python:3.11-slim-bookworm
# Domain: pyswisseph (C ext), CairoSVG (SVG→PNG cards), CJK fonts
# ──────────────────────────────────────────────────────────────────────────────

ARG PYTHON_VERSION=3.11

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        libcairo2-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY pyproject.toml ./

RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        fontconfig \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        fonts-noto-color-emoji \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        ca-certificates \
        curl \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

RUN useradd --create-home --uid 1000 --shell /bin/bash app

WORKDIR /app
COPY --chown=app:app . /app

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import bot.config" || exit 1
