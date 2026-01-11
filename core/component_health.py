"""
System Health Monitoring & Status Tracking

Provides centralized health status for all components,
allowing the dashboard and other consumers to query system state.
"""

import logging
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional, List
from threading import Lock, RLock

# Import resource monitor for system health integration
from core.resource_monitor import get_resource_monitor

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels for components."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    last_updated: datetime
    error_count: int = 0
    warning_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    fallback_active: bool = False
    metadata: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_updated": self.last_updated.isoformat(),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "fallback_active": self.fallback_active,
            "metadata": self.metadata or {},
        }


class SystemHealthMonitor:
    """
    Centralized health monitoring for all AstraGuard components.
    
    Thread-safe singleton that tracks component health and allows
    queries about system state.
    """
    
    _instance: Optional['SystemHealthMonitor'] = None
    _init_lock = Lock()
    
    def __new__(cls):
        """Implement singleton pattern with proper locking."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize health monitor (idempotent)."""
        if getattr(self, '_initialized', False):
            return
        
        self._initialized = True
        self._components: Dict[str, ComponentHealth] = {}
        self._component_lock = RLock()  # Use RLock for reentrant access
        self._system_status = HealthStatus.HEALTHY
        logger.debug("SystemHealthMonitor initialized")
    
    def register_component(self, name: str, metadata: Optional[Dict] = None):
        """
        Register a new component for monitoring.
        
        Args:
            name: Component name
            metadata: Optional metadata about the component
        """
        with self._component_lock:
            self._components[name] = ComponentHealth(
                name=name,
                status=HealthStatus.HEALTHY,
                last_updated=datetime.now(),
                metadata=metadata or {},
            )
            logger.debug(f"Registered component: {name}")
    
    def mark_healthy(self, component: str, metadata: Optional[Dict] = None):
        """
        Mark a component as healthy.
        
        Args:
            component: Component name
            metadata: Optional metadata update
        """
        with self._component_lock:
            if component not in self._components:
                self.register_component(component, metadata)
            
            health = self._components[component]
            health.status = HealthStatus.HEALTHY
            health.last_updated = datetime.now()
            health.fallback_active = False
            if metadata:
                health.metadata.update(metadata)
            
            self._update_system_status()
            logger.debug(f"Component {component} marked healthy")
    
    def mark_degraded(self, component: str, error_msg: Optional[str] = None,
                      fallback_active: bool = True, metadata: Optional[Dict] = None):
        """
        Mark a component as degraded.
        
        Args:
            component: Component name
            error_msg: Optional error message
            fallback_active: Whether fallback is active
            metadata: Optional metadata update
        """
        with self._component_lock:
            if component not in self._components:
                self.register_component(component, metadata)
            
            health = self._components[component]
            health.status = HealthStatus.DEGRADED
            health.warning_count += 1
            health.last_error = error_msg
            health.last_error_time = datetime.now()
            health.last_updated = datetime.now()
            health.fallback_active = fallback_active
            if metadata:
                health.metadata.update(metadata)
            
            self._update_system_status()
            logger.warning(f"Component {component} marked degraded: {error_msg}")
    
    def mark_failed(self, component: str, error_msg: Optional[str] = None,
                    metadata: Optional[Dict] = None):
        """
        Mark a component as failed.
        
        Args:
            component: Component name
            error_msg: Optional error message
            metadata: Optional metadata update
        """
        with self._component_lock:
            if component not in self._components:
                self.register_component(component, metadata)
            
            health = self._components[component]
            health.status = HealthStatus.FAILED
            health.error_count += 1
            health.last_error = error_msg
            health.last_error_time = datetime.now()
            health.last_updated = datetime.now()
            if metadata:
                health.metadata.update(metadata)
            
            self._update_system_status()
            logger.error(f"Component {component} marked failed: {error_msg}")
    
    def _update_system_status(self):
        """Update overall system status based on component statuses."""
        if not self._components:
            self._system_status = HealthStatus.UNKNOWN
            return
        
        statuses = [c.status for c in self._components.values()]
        
        if any(s == HealthStatus.FAILED for s in statuses):
            self._system_status = HealthStatus.DEGRADED  # System is degraded if any component fails
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            self._system_status = HealthStatus.DEGRADED
        else:
            self._system_status = HealthStatus.HEALTHY
    
    def get_component_health(self, component: str) -> ComponentHealth:
        """
        Get health status of a specific component.
        
        Args:
            component: Component name
        
        Returns:
            ComponentHealth object (auto-registers with UNKNOWN if not found)
        """
        with self._component_lock:
            # Auto-register if not found to ensure never-None contract
            if component not in self._components:
                self._components[component] = ComponentHealth(
                    name=component,
                    status=HealthStatus.UNKNOWN,
                    last_updated=datetime.now(),
                    metadata={},
                )
                logger.debug(f"Auto-registered component {component} with UNKNOWN status")
            return self._components[component]
    
    def get_all_health(self) -> Dict[str, Dict]:
        """
        Get health status of all components.
        
        Returns:
            Dictionary mapping component names to their health dicts
        """
        with self._component_lock:
            health_data = {name: health.to_dict() for name, health in self._components.items()}
            
            # Add resource monitoring as a system component
            try:
                resource_monitor = get_resource_monitor()
                resource_status = resource_monitor.check_resource_health()
                
                # Map resource status to component health status
                resource_health_status = HealthStatus.HEALTHY
                if resource_status.get('overall') == 'critical':
                    resource_health_status = HealthStatus.FAILED
                elif resource_status.get('overall') == 'warning':
                    resource_health_status = HealthStatus.DEGRADED
                
                # Get current metrics for metadata
                metrics = resource_monitor.get_current_metrics()
                
                resource_component = ComponentHealth(
                    name="system_resources",
                    status=resource_health_status,
                    last_updated=datetime.now(),
                    metadata={
                        "cpu_percent": round(metrics.cpu_percent, 1),
                        "memory_percent": round(metrics.memory_percent, 1),
                        "disk_percent": round(metrics.disk_usage_percent, 1),
                        "memory_available_mb": round(metrics.memory_available_mb, 0),
                        "resource_status": resource_status
                    }
                )
                
                health_data["system_resources"] = resource_component.to_dict()
                
            except Exception as e:
                logger.warning(f"Failed to get resource health: {e}")
                # Add resource component with unknown status if monitoring fails
                resource_component = ComponentHealth(
                    name="system_resources",
                    status=HealthStatus.UNKNOWN,
                    last_updated=datetime.now(),
                    last_error=str(e),
                    metadata={"error": "Resource monitoring unavailable"}
                )
                health_data["system_resources"] = resource_component.to_dict()
            
            return health_data
    
    def get_resource_health(self) -> Dict:
        """
        Get detailed resource health information.
        
        Returns:
            Dictionary with resource metrics and health status
        """
        try:
            resource_monitor = get_resource_monitor()
            resource_status = resource_monitor.check_resource_health()
            current_metrics = resource_monitor.get_current_metrics()
            
            return {
                "status": resource_status.get('overall', 'unknown'),
                "metrics": current_metrics.to_dict(),
                "thresholds": {
                    "cpu_warning": resource_monitor.thresholds.cpu_warning,
                    "cpu_critical": resource_monitor.thresholds.cpu_critical,
                    "memory_warning": resource_monitor.thresholds.memory_warning,
                    "memory_critical": resource_monitor.thresholds.memory_critical,
                    "disk_warning": resource_monitor.thresholds.disk_warning,
                    "disk_critical": resource_monitor.thresholds.disk_critical,
                },
                "component_status": resource_status,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get resource health details: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_system_status(self) -> Dict:
        """
        Get overall system health status.
        
        Returns:
            Dictionary with system-level health info
        """
        with self._component_lock:
            healthy_count = sum(1 for c in self._components.values() 
                              if c.status == HealthStatus.HEALTHY)
            degraded_count = sum(1 for c in self._components.values() 
                               if c.status == HealthStatus.DEGRADED)
            failed_count = sum(1 for c in self._components.values() 
                             if c.status == HealthStatus.FAILED)
            
            return {
                "overall_status": self._system_status.value,
                "timestamp": datetime.now().isoformat(),
                "component_counts": {
                    "healthy": healthy_count,
                    "degraded": degraded_count,
                    "failed": failed_count,
                    "total": len(self._components),
                },
                "components": self.get_all_health(),
            }
    
    def is_system_healthy(self) -> bool:
        """Check if system is in healthy state."""
        with self._component_lock:
            return self._system_status == HealthStatus.HEALTHY
    
    def is_system_degraded(self) -> bool:
        """Check if system is in degraded state."""
        with self._component_lock:
            return self._system_status == HealthStatus.DEGRADED
    
    def reset(self):
        """Reset all health monitoring (for testing)."""
        with self._component_lock:
            self._components.clear()
            self._system_status = HealthStatus.HEALTHY
            # Allow reinitialization after reset
            self._initialized = False
            logger.info("Health monitor reset")
        
        # CRITICAL: Reset singleton instance to allow fresh creation
        # This ensures new instances get properly initialized after reset
        with self._init_lock:
            SystemHealthMonitor._instance = None
            # Also reset the module-level _health_monitor
            global _health_monitor
            _health_monitor = None


# Global instance - get via get_health_monitor()
_health_monitor = None


def get_health_monitor() -> SystemHealthMonitor:
    """Get the global health monitor instance (singleton)."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SystemHealthMonitor()
    return _health_monitor
