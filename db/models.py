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


# ── Models ────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(sa.String(64))
    first_name: Mapped[str] = mapped_column(sa.String(128))
    locale: Mapped[str] = mapped_column(sa.String(8), default="ru", server_default="ru")
    free_question_used: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="charts", lazy="raise")
    consultations: Mapped[list["Consultation"]] = relationship(
        back_populates="chart", lazy="raise", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="chart", lazy="raise", cascade="all, delete-orphan"
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
