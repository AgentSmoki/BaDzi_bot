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
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Install OpenMoji Color (CBDT bitmap build) as the primary color emoji
# font. Apple's emoji is licensed for macOS only; Twemoji (Mozilla COLR
# build) was the prior fallback but rendered flat and dim — the У-син
# wheel emojis (🌳🔥⛰⚙💧) looked washed out on prod. OpenMoji has more
# saturated palette, larger glyph metrics, and the CBDT (bitmap) build
# specifically gives a stylized/dimensional look that's closer to
# Apple's 3D-ish appearance than COLR-vector alternatives.
#
# License: CC-BY-SA 4.0 (font assets only — attribution kept in this
# Dockerfile + README, no impact on bot code licensing since rendered
# PNGs don't constitute a derivative work of the font under copyright).
#
# We extract only the CBDT TTF variant (best Pango compatibility on
# Bookworm) — the zip also contains picosvgz/sbix/COLR builds that we
# skip to keep the image lean.
RUN mkdir -p /usr/share/fonts/truetype/openmoji \
    && curl -fsSL "https://github.com/hfg-gmuend/openmoji/releases/download/17.0.0/openmoji-font.zip" \
        -o /tmp/openmoji.zip \
    && cd /tmp && unzip -q openmoji.zip "OpenMoji-color-cbdt/OpenMoji-color-cbdt.ttf" \
    && mv /tmp/OpenMoji-color-cbdt/OpenMoji-color-cbdt.ttf /usr/share/fonts/truetype/openmoji/ \
    && rm -rf /tmp/openmoji.zip /tmp/OpenMoji-color-cbdt

# Fontconfig aliases — redirect macOS-native font names referenced in
# the SVG template (PingFang SC, Hiragino, Apple Color Emoji, ...) to
# the open-source equivalents above. Without this, fc-match falls
# through to DejaVu Sans for any unknown CJK family and the chart
# renders tofu boxes for every Chinese glyph (root cause of the prod
# regression). fc-cache -fv runs after the alias is in place so the
# resolution is baked into the image layer.
COPY docker/fontconfig/99-bazi-aliases.conf /etc/fonts/conf.d/99-bazi-aliases.conf
RUN fc-cache -fv

COPY --from=builder /opt/venv /opt/venv

RUN useradd --create-home --uid 1000 --shell /bin/bash app

WORKDIR /app
COPY --chown=app:app . /app

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import bot.config" || exit 1
