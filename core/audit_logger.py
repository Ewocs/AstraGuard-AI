"""
Audit Logger for AstraGuard AI

Provides centralized audit logging for security events, access attempts,
configuration changes, and compliance tracking.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum


class AuditEventType(Enum):
    """Types of audit events."""
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    ACCESS_DENIED = "access_denied"
    CONFIG_CHANGE = "config_change"
    PHASE_CHANGE = "phase_change"
    CHAOS_INJECTION = "chaos_injection"
    API_ACCESS = "api_access"
    ADMIN_ACTION = "admin_action"
    SECURITY_VIOLATION = "security_violation"


class AuditLogger:
    """Centralized audit logger for security events."""

    def __init__(self, log_file: str = "logs/audit.log", max_bytes: int = 10*1024*1024, backup_count: int = 5):
        """
        Initialize the audit logger.

        Args:
            log_file: Path to the audit log file
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
        """
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        # Ensure logs directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Create logger
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)

        # Remove any existing handlers
        self.logger.handlers.clear()

        # Create rotating file handler
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )

        # Create formatter for audit logs
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(event_type)s - %(user)s - %(ip)s - %(resource)s - %(action)s - %(details)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def log_event(
        self,
        event_type: AuditEventType,
        user: str = "unknown",
        ip: str = "unknown",
        resource: str = "",
        action: str = "",
        details: Dict[str, Any] = None,
        level: int = logging.INFO
    ):
        """
        Log an audit event.

        Args:
            event_type: Type of audit event
            user: User performing the action
            ip: IP address of the request
            resource: Resource being accessed/modified
            action: Action performed
            details: Additional details as dict
            level: Logging level
        """
        details_str = ""
        if details:
            details_str = str(details).replace('\n', ' ').replace('\r', ' ')

        # Create log message with structured data
        extra = {
            'event_type': event_type.value,
            'user': user,
            'ip': ip,
            'resource': resource,
            'action': action,
            'details': details_str
        }

        self.logger.log(level, f"AUDIT: {event_type.value}", extra=extra)

    def log_auth_success(self, user: str, ip: str = "unknown", method: str = "unknown"):
        """Log successful authentication."""
        self.log_event(
            AuditEventType.AUTH_SUCCESS,
            user=user,
            ip=ip,
            resource="authentication",
            action="login",
            details={"method": method}
        )

    def log_auth_failure(self, user: str, ip: str = "unknown", reason: str = "unknown"):
        """Log failed authentication."""
        self.log_event(
            AuditEventType.AUTH_FAILURE,
            user=user,
            ip=ip,
            resource="authentication",
            action="login_attempt",
            details={"reason": reason},
            level=logging.WARNING
        )

    def log_access_denied(self, user: str, ip: str, resource: str, required_permission: str = ""):
        """Log access denied events."""
        self.log_event(
            AuditEventType.ACCESS_DENIED,
            user=user,
            ip=ip,
            resource=resource,
            action="access_denied",
            details={"required_permission": required_permission},
            level=logging.WARNING
        )

    def log_config_change(self, user: str, ip: str, config_key: str, old_value: Any = None, new_value: Any = None):
        """Log configuration changes."""
        self.log_event(
            AuditEventType.CONFIG_CHANGE,
            user=user,
            ip=ip,
            resource="configuration",
            action="change",
            details={
                "config_key": config_key,
                "old_value": str(old_value),
                "new_value": str(new_value)
            }
        )

    def log_phase_change(self, user: str, ip: str, old_phase: str, new_phase: str, force: bool = False):
        """Log mission phase changes."""
        self.log_event(
            AuditEventType.PHASE_CHANGE,
            user=user,
            ip=ip,
            resource="mission_phase",
            action="change",
            details={
                "old_phase": old_phase,
                "new_phase": new_phase,
                "force": force
            }
        )

    def log_chaos_injection(self, user: str, ip: str, fault_type: str, duration: int):
        """Log chaos engineering injections."""
        self.log_event(
            AuditEventType.CHAOS_INJECTION,
            user=user,
            ip=ip,
            resource="chaos_engine",
            action="inject_fault",
            details={
                "fault_type": fault_type,
                "duration_seconds": duration
            },
            level=logging.WARNING
        )

    def log_api_access(self, user: str, ip: str, endpoint: str, method: str, status_code: int):
        """Log API access."""
        self.log_event(
            AuditEventType.API_ACCESS,
            user=user,
            ip=ip,
            resource=endpoint,
            action=method,
            details={"status_code": status_code}
        )

    def log_admin_action(self, user: str, ip: str, action: str, details: Dict[str, Any] = None):
        """Log administrative actions."""
        self.log_event(
            AuditEventType.ADMIN_ACTION,
            user=user,
            ip=ip,
            resource="admin",
            action=action,
            details=details
        )

    def log_security_violation(self, user: str, ip: str, violation_type: str, details: Dict[str, Any] = None):
        """Log security violations."""
        self.log_event(
            AuditEventType.SECURITY_VIOLATION,
            user=user,
            ip=ip,
            resource="security",
            action="violation",
            details={"violation_type": violation_type, **(details or {})},
            level=logging.ERROR
        )


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def init_audit_logging(log_file: str = "logs/audit.log", max_bytes: int = 10*1024*1024, backup_count: int = 5):
    """Initialize audit logging with custom settings."""
    global _audit_logger
    _audit_logger = AuditLogger(log_file, max_bytes, backup_count)
    return _audit_logger