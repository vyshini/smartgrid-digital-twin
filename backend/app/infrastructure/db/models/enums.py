"""
Python enums mirroring the Postgres ENUM types defined in
docs/database-schema.sql. Kept centralized so ORM columns and Pydantic
schemas both import from one place instead of duplicating string literals.
"""
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    GRID_OPERATOR = "grid_operator"
    ENGINEER = "engineer"
    RESEARCHER = "researcher"


class NodeStatus(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


class LineStatus(str, enum.Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
