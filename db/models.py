import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

# ── Enums ─────────────────────────────────────────────────────────────────────


class SubscriptionPlan(str, enum.Enum):
    free = "free"
    single = "single"
    session = "session"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class ForecastKind(str, enum.Enum):
    """Wave 3 — what the user paid for.

    - ``monthly``: «Прогноз на месяц», 500 ₽. Delivery: either four weekly
      chunks (``MonthlyDelivery.weekly``) or one bulk message
      (``MonthlyDelivery.bulk``).
    - ``daily``: «Прогноз дня + активации», 900 ₽/month, fires every
      morning at 04:00 local-to-chart-tz.
    """

    monthly = "monthly"
    daily = "daily"


class MonthlyDelivery(str, enum.Enum):
    """Only meaningful when ``ForecastKind.monthly``. NULL for ``daily``.

    ``weekly`` — bot sends 4 chunks at 7-day intervals starting from
    ``started_at``. ``bulk`` — one big payload right after purchase
    (still re-rendered per chart so it carries personalised energies)."""

    weekly = "weekly"
    bulk = "bulk"


class MasterMeetingStatus(str, enum.Enum):
    """Wave 5 — lifecycle of a master-meeting transcription job."""

    queued = "queued"
    transcribing = "transcribing"
    ready = "ready"
    failed = "failed"


class MasterMeetingSource(str, enum.Enum):
    """Wave 5 — where the meeting recording lives.

    Heuristic-detected from URL hostname so we can pick the right
    download / transcribe path. ``other`` is the catch-all for direct
    audio/video URLs that don't match a known cloud."""

    youtube = "youtube"
    gdrive = "gdrive"
    ydisk = "ydisk"
    cloud_mail = "cloud_mail"
    zoom = "zoom"
    tg_file = "tg_file"
    other = "other"


class JournalEntrySource(str, enum.Enum):
    """Wave 4 — where a journal entry came from.

    - ``text``: typed reflection
    - ``voice``: voice message transcribed via TeleTranscribe MCP
    - ``auto``: bot-generated entry on an important date when the
      user didn't reply within the day (so the calendar history isn't
      patchy)
    """

    text = "text"
    voice = "voice"
    auto = "auto"


# ── Models ────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(sa.String(64))
    first_name: Mapped[str] = mapped_column(sa.String(128))
    locale: Mapped[str] = mapped_column(sa.String(8), default="ru", server_default="ru")
    # Wave 7 UX rework (2026-05-24): counter вместо bool. Default 0 =
    # «бесплатных вопросов потрачено». Лимит держится в settings
    # (по умолчанию 3). 4-й вопрос → pricing_kb. Поле free_question_used
    # удалено миграцией 2026-05-24_<rev>.
    free_questions_used: Mapped[int] = mapped_column(
        sa.Integer, default=0, server_default=sa.text("0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    charts: Mapped[list["Chart"]] = relationship(
        back_populates="user", lazy="raise", cascade="all, delete-orphan"
    )
    consultations: Mapped[list["Consultation"]] = relationship(
        back_populates="user", lazy="raise", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user",
        lazy="raise",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Chart(Base):
    __tablename__ = "charts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str | None] = mapped_column(sa.String(128))
    birth_datetime_utc: Mapped[datetime]
    birth_datetime_original: Mapped[datetime]
    latitude: Mapped[float] = mapped_column(sa.Double)
    longitude: Mapped[float] = mapped_column(sa.Double)
    tz_offset: Mapped[float] = mapped_column(sa.Double)
    early_rat: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    hidden_stems_school: Mapped[str] = mapped_column(
        sa.String(32), default="traditional", server_default="traditional"
    )
    chart_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    has_birth_time: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    # Wave 6 / ADR-010: self-FK to another chart of the same user representing
    # the «partner» counterpart for the relationships skill. NULL = no partner
    # linked yet; ondelete=SET NULL so deleting the partner doesn't cascade
    # and kill the owner chart.
    partner_chart_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("charts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="charts", lazy="raise")
    consultations: Mapped[list["Consultation"]] = relationship(
        back_populates="chart", lazy="raise", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="chart", lazy="raise", cascade="all, delete-orphan"
    )
    partner_chart: Mapped["Chart | None"] = relationship(
        "Chart",
        foreign_keys=[partner_chart_id],
        remote_side="Chart.id",
        lazy="raise",
        post_update=True,
    )


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    chart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("charts.id", ondelete="CASCADE"),
        index=True,
    )
    topic: Mapped[str | None] = mapped_column(sa.String(128))
    user_message: Mapped[str] = mapped_column(sa.Text)
    ai_response: Mapped[str] = mapped_column(sa.Text)
    model_used: Mapped[str] = mapped_column(sa.String(128))
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 6), default=Decimal("0"))
    latency_ms: Mapped[int] = mapped_column(default=0)
    trace_id: Mapped[str] = mapped_column(sa.String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="consultations", lazy="raise")
    chart: Mapped[Chart] = relationship(back_populates="consultations", lazy="raise")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        sa.Enum(SubscriptionPlan, native_enum=False, length=16),
        default=SubscriptionPlan.free,
        server_default=SubscriptionPlan.free.value,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        sa.Enum(SubscriptionStatus, native_enum=False, length=16),
        default=SubscriptionStatus.active,
        server_default=SubscriptionStatus.active.value,
    )
    questions_remaining: Mapped[int | None] = mapped_column(sa.Integer)
    session_expires_at: Mapped[datetime | None]
    monthly_expires_at: Mapped[datetime | None]
    payment_provider: Mapped[str | None] = mapped_column(sa.String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="subscription", lazy="raise")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    chart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("charts.id", ondelete="CASCADE"),
        index=True,
    )
    event_date: Mapped[date]
    event_type: Mapped[str] = mapped_column(sa.String(64))
    description: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    chart: Mapped[Chart] = relationship(back_populates="events", lazy="raise")


class ChartForecastSubscription(Base):
    """Wave 3 — per-chart paid forecast subscription (separate from the
    main consultation subscription which lives in ``subscriptions`` and
    is per-user, not per-chart).

    One row = one active forecast plan attached to one chart.
    Re-buying creates a new row (history-preserving); the active set is
    selected with ``WHERE status='active' AND expires_at>now()``.
    """

    __tablename__ = "chart_forecast_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    chart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("charts.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[ForecastKind] = mapped_column(
        sa.Enum(ForecastKind, native_enum=False, length=16),
        index=True,
    )
    # NULL for `daily`; one of `weekly`/`bulk` for `monthly`.
    monthly_delivery: Mapped[MonthlyDelivery | None] = mapped_column(
        sa.Enum(MonthlyDelivery, native_enum=False, length=16),
        nullable=True,
    )
    # For `daily` — what hour (UTC) the bot fires the send. Chosen by the
    # user as «04:00 моего времени» and converted to UTC using the chart's
    # tz_offset at purchase time. Re-conversion on DST shifts handled by
    # the scheduler. NULL for monthly.
    daily_send_hour_utc: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        sa.Enum(SubscriptionStatus, native_enum=False, length=16),
        default=SubscriptionStatus.active,
        server_default=SubscriptionStatus.active.value,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    price_rub: Mapped[int] = mapped_column(sa.Integer)
    # `free_dev_bypass` while ЮKassa isn't connected (Wave 3 launch);
    # `yookassa` after 1.12.3. NULL = unknown / migrated row.
    payment_provider: Mapped[str | None] = mapped_column(sa.String(32))
    # Wave 7 Phase 2 ext (2026-05-26) — школа интерпретации
    # ("classic" | "edoha" | "modern"). Forecast.py подгружает
    # base_<school>.md поверх base.md, как и консультации.
    chosen_school: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="classic"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(lazy="raise")
    chart: Mapped[Chart] = relationship(lazy="raise")
    deliveries: Mapped[list["ForecastDelivery"]] = relationship(
        back_populates="subscription", lazy="raise", cascade="all, delete-orphan"
    )


class ChartJournalSettings(Base):
    """Wave 4 — per-chart toggle + reminder schedule for the daily
    reflection journal.

    One row per chart (UNIQUE on chart_id). ``enabled=False`` is the
    default — the user opts in via «📔 Дневник» button. ``reminder_hour_utc``
    is derived from ``reminder_hour_local`` + ``chart.tz_offset`` at the
    moment of save; recalculated only when the user changes the hour
    (not on DST shifts — that's a future cleanup task).
    """

    __tablename__ = "chart_journal_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    chart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("charts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    reminder_hour_local: Mapped[int] = mapped_column(sa.Integer, default=21, server_default="21")
    reminder_hour_utc: Mapped[int] = mapped_column(sa.Integer, default=18, server_default="18")
    # Wave 4e — Bogdan acts as a personal astrologer who pre-warns about
    # natal Шэнь Ша resonances on upcoming dates (за 2 дня + в день).
    # Default ON so the user gets value without configuring; can be turned
    # off via /start «🌟 Важные даты: ON/OFF» button.
    important_dates_enabled: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    # Rate limit: scheduler skips this chart if last alert was <7 days
    # ago. NULL = never alerted; first scan will pick the earliest
    # significant date.
    last_important_date_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class JournalEntry(Base):
    """Wave 4 — one reflection per chart per day.

    UNIQUE(chart_id, entry_date) — re-writing the same day overwrites
    the row (handled at repository layer with UPSERT). ``source`` tracks
    whether the user actually responded or the bot auto-logged the
    day's energies on an important date.
    """

    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    chart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("charts.id", ondelete="CASCADE"),
        index=True,
    )
    entry_date: Mapped[date]
    energies_summary: Mapped[str] = mapped_column(sa.Text)
    """Auto-computed pillars + active stars for the day. Always filled
    even when the user didn't reflect — gives the export readability."""
    user_reflection: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    """User's actual words. NULL when source=auto."""
    source: Mapped[JournalEntrySource] = mapped_column(
        sa.Enum(JournalEntrySource, native_enum=False, length=16),
        default=JournalEntrySource.text,
        server_default=JournalEntrySource.text.value,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        sa.UniqueConstraint("chart_id", "entry_date", name="uq_journal_entries_chart_date"),
    )


class MasterMeeting(Base):
    """Wave 5 — recording of a session with a flesh-and-blood master.

    Anastasia (the AI) uses the transcript + LLM-extractive summary as
    additional context (``[MASTER_MEETING_NOTES]`` section) when the
    user asks a question — so deeper insights from real sessions feed
    into bot answers.

    One chart can have many meetings. Status fields let the bot show
    «расшифровываю…» while the background task runs."""

    __tablename__ = "master_meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    chart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("charts.id", ondelete="CASCADE"),
        index=True,
    )
    source_url: Mapped[str] = mapped_column(sa.Text)
    source_type: Mapped[MasterMeetingSource] = mapped_column(
        sa.Enum(MasterMeetingSource, native_enum=False, length=16),
        default=MasterMeetingSource.other,
        server_default=MasterMeetingSource.other.value,
    )
    title: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)
    transcript: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    """Filled when ``status='ready'``. NULL while queued/transcribing or
    if status='failed' (use ``error`` to diagnose)."""
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    """LLM-extractive summary — themes, recommendations, techniques.
    Injected into compose_messages as [MASTER_MEETING_NOTES]."""
    status: Mapped[MasterMeetingStatus] = mapped_column(
        sa.Enum(MasterMeetingStatus, native_enum=False, length=16),
        default=MasterMeetingStatus.queued,
        server_default=MasterMeetingStatus.queued.value,
        index=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    transcribed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ForecastDelivery(Base):
    """Wave 3 — record of one forecast send. Used by the scheduler for
    dedup (don't fire twice for the same scheduled slot if the worker
    restarts) and by the user-facing «history of forecasts» screen.

    ``slot_key`` is a deterministic string for the scheduled occurrence
    so the unique constraint blocks duplicates. Examples:
    - daily: ``daily:2026-05-19``
    - monthly weekly: ``monthly:2026-05:week3``
    - monthly bulk: ``monthly:2026-05:bulk``
    """

    __tablename__ = "forecast_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("chart_forecast_subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    slot_key: Mapped[str] = mapped_column(sa.String(64), index=True)
    content: Mapped[str] = mapped_column(sa.Text)
    """Rendered LLM body in Telegram-ready HTML."""
    sent_at: Mapped[datetime | None]
    """NULL while queued; set when actually delivered."""
    error: Mapped[str | None] = mapped_column(sa.Text)
    """Filled when send failed (Telegram API error, user blocked bot, etc)."""
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    subscription: Mapped[ChartForecastSubscription] = relationship(
        back_populates="deliveries", lazy="raise"
    )

    __table_args__ = (
        sa.UniqueConstraint("subscription_id", "slot_key", name="uq_forecast_deliveries_slot"),
    )
