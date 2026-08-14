"""ORM models for control-plane metadata (Phase 2 + Phase 4 hosts/alerts/licenses)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantRow(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    api_keys: Mapped[list[ApiKeyRow]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    instances: Mapped[list[InstanceRow]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    route_policy: Mapped[RoutePolicyRow | None] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    licenses: Mapped[list[LicenseRow]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class ApiKeyRow(Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("key_hash", name="uq_api_keys_hash"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    rpm_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    allowed_models: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[TenantRow] = relationship(back_populates="api_keys")


class RoutePolicyRow(Base):
    __tablename__ = "route_policies"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="hybrid")
    # hybrid thresholds (chars / estimated tokens)
    short_max_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=800)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped[TenantRow] = relationship(back_populates="route_policy")


class HostRow(Base):
    """Customer-owned SSH target (Phase 4 remote provider)."""

    __tablename__ = "hosts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    ssh_host: Mapped[str] = mapped_column(String(256), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    ssh_user: Mapped[str] = mapped_column(String(128), nullable=False, default="ubuntu")
    # Path on the control-plane machine to an SSH private key (never the key bytes).
    identity_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    # unknown | online | offline | simulated | installed
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    instances: Mapped[list[InstanceRow]] = relationship(back_populates="host")


class InstanceRow(Base):
    __tablename__ = "instances"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    preset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    # created | running | stopped | sleeping | error
    backend: Mapped[str] = mapped_column(String(32), nullable=False, default="ollama")
    compose_project: Mapped[str | None] = mapped_column(String(128), nullable=True)
    host_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped[TenantRow] = relationship(back_populates="instances")
    host: Mapped[HostRow | None] = relationship(back_populates="instances")


class AlertRow(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_alerts_fingerprint"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warn")
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    # open | acked | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LicenseRow(Base):
    """Vertical mirror / pack license issued to a tenant (Phase 4)."""

    __tablename__ = "licenses"
    __table_args__ = (UniqueConstraint("key_hash", name="uq_licenses_hash"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    # active | revoked | expired
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped[TenantRow] = relationship(back_populates="licenses")


class UsageEventRow(Base):
    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route: Mapped[str] = mapped_column(String(16), nullable=False)  # local | cloud | vllm
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
