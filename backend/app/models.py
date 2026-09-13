"""Esquemas Pydantic para la API de StatusSense."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

MonitorType = Literal["http", "tcp", "ping", "dns"]
IncidentType = Literal["sudden_outage", "progressive_degradation"]
ChannelType = Literal["telegram", "webhook"]


class MonitorCreate(BaseModel):
    name: str
    type: MonitorType
    target: str
    interval_seconds: int = Field(default=60, ge=5)
    timeout_seconds: float = Field(default=10.0, gt=0)
    degradation_weight: float = 0.3
    variance_weight: float = 0.2
    uptime_weight: float = 0.5
    active: bool = True


class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    target: Optional[str] = None
    interval_seconds: Optional[int] = Field(default=None, ge=5)
    timeout_seconds: Optional[float] = Field(default=None, gt=0)
    degradation_weight: Optional[float] = None
    variance_weight: Optional[float] = None
    uptime_weight: Optional[float] = None
    active: Optional[bool] = None


class MonitorOut(BaseModel):
    id: int
    name: str
    type: MonitorType
    target: str
    interval_seconds: int
    timeout_seconds: float
    degradation_weight: float
    variance_weight: float
    uptime_weight: float
    active: bool
    created_at: str
    health_score: Optional[float] = None
    status: Optional[str] = None
    last_check_at: Optional[str] = None


class CheckOut(BaseModel):
    id: int
    monitor_id: int
    timestamp: str
    success: bool
    latency_ms: Optional[float]
    http_status: Optional[int]
    error_message: Optional[str]


class HealthSnapshotOut(BaseModel):
    id: int
    monitor_id: int
    timestamp: str
    health_score: float
    uptime_pct: Optional[float]
    trend_slope: Optional[float]
    variance_ratio: Optional[float]


class IncidentOut(BaseModel):
    id: int
    monitor_id: int
    started_at: str
    resolved_at: Optional[str]
    incident_type: Optional[IncidentType]
    min_health_score: Optional[float]


class NotificationChannelCreate(BaseModel):
    type: ChannelType
    name: str = ""
    config: dict[str, Any]
    active: bool = True


class NotificationChannelOut(BaseModel):
    id: int
    type: ChannelType
    name: str
    config: dict[str, Any]
    active: bool


class ExportBundle(BaseModel):
    version: int = 1
    exported_at: str
    monitors: list[MonitorCreate]
    notification_channels: list[NotificationChannelCreate]


class ImportResult(BaseModel):
    monitors_imported: int
    channels_imported: int
