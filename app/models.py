from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./heatguard.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)  # psycopg 3

engine = create_engine(DATABASE_URL, pool_pre_ping=True,
                       connect_args={"check_same_thread": False}
                       if DATABASE_URL.startswith("sqlite")
                       # a hard connect timeout: a stuck TLS/pooler handshake must fail fast,
                       # not hang the app's startup forever
                       else {"connect_timeout": 10})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(2))         # ISO code: AE, PK
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    tz_offset_s: Mapped[int] = mapped_column(Integer, default=0)
    weather: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weather_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    weather_status: Mapped[str] = mapped_column(String(20), default="none")  # live|cache|fallback|sim
    weather_error: Mapped[str] = mapped_column(Text, default="")
    sim: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    crews: Mapped[list[Crew]] = relationship(back_populates="site", order_by="Crew.id")


class Crew(Base):
    __tablename__ = "crews"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    name: Mapped[str] = mapped_column(String(80))
    task: Mapped[str] = mapped_column(String(120), default="")
    workload: Mapped[str] = mapped_column(String(12), default="moderate")
    clothing: Mapped[str] = mapped_column(String(20), default="standard")
    acclimatised_days: Mapped[int] = mapped_column(Integer, default=14)
    shaded: Mapped[bool] = mapped_column(Boolean, default=False)
    shift_start: Mapped[str] = mapped_column(String(5), default="06:00")
    shift_end: Mapped[str] = mapped_column(String(5), default="18:00")
    current: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # last outlook
    last_alert_level: Mapped[int] = mapped_column(Integer, default=-1)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    site: Mapped[Site] = relationship(back_populates="crews")
    people: Mapped[list[Person]] = relationship(back_populates="crew", order_by="Person.id")


class Person(Base):
    __tablename__ = "people"
    id: Mapped[int] = mapped_column(primary_key=True)
    crew_id: Mapped[int | None] = mapped_column(ForeignKey("crews.id"), nullable=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(16))           # worker | supervisor | first_aider
    first_name: Mapped[str] = mapped_column(String(40))
    phone: Mapped[str] = mapped_column(String(24), unique=True)
    language: Mapped[str] = mapped_column(String(2), default="en")
    consent: Mapped[str] = mapped_column(String(10), default="pending")  # pending | yes | no
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    crew: Mapped[Crew | None] = relationship(back_populates="people")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"))
    direction: Mapped[str] = mapped_column(String(3))       # out | in
    kind: Mapped[str] = mapped_column(String(16))           # consent|alert|warning|escalation|reply|info
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    buttons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    delivery: Mapped[str] = mapped_column(String(16), default="outbox")  # outbox|sent|failed|received
    delivery_error: Mapped[str] = mapped_column(Text, default="")


class CheckIn(Base):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"))
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"))
    level: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime)
    due_at: Mapped[datetime] = mapped_column(DateTime)
    reply: Mapped[str | None] = mapped_column(String(10), nullable=True)   # ok | unwell
    replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[int] = mapped_column(primary_key=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"))
    reason: Mapped[str] = mapped_column(String(10))         # unwell | no_reply
    level: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str] = mapped_column(String(40), default="")


class Warning(Base):
    """A look-ahead warning, later checked against what actually happened."""
    __tablename__ = "warnings"
    id: Mapped[int] = mapped_column(primary_key=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime)
    predicted_level: Mapped[int] = mapped_column(Integer)
    predicted_for: Mapped[datetime] = mapped_column(DateTime)   # UTC
    actual_level: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    crew_id: Mapped[int] = mapped_column(ForeignKey("crews.id"))
    at: Mapped[datetime] = mapped_column(DateTime)
    level: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(10))


def init_db():
    Base.metadata.create_all(engine)
