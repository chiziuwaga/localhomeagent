"""
Thermodynamic Energy Model for AI Agent Security
Based on the project's core philosophy: Model system states as energy landscape
to enforce rules about which energy levels are acceptable for security and agent control.

Energy function:
E = α·(security_risk) + β·(behavior_surprise) + γ·(resource_cost)

Where:
- security_risk: How dangerous the requested action is (unlock door = high, turn on light = low)
- behavior_surprise: How off-pattern this is vs historical behavior
- resource_cost: How heavy the operation is (big LLM call, multi-tool chain = high)

Energy thresholds:
- Low E → Just do it
- Medium E → Ask for confirmation / extra context
- High E → Force challenge + voice verification + notify admin
- Very high E → Auto-deny + alert

Features:
- F4.3.1-6: Core energy model (implemented)
- F4.3.7: Voice verification trigger
- F4.3.8: Admin notification
- F4.3.9: Energy audit log
- F4.3.10: Energy dashboard visualization
"""

import logging
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EnergyLevel(Enum):
    LOW = "low"           # Safe: execute immediately
    MEDIUM = "medium"     # Caution: request confirmation
    HIGH = "high"         # Danger: require verification + notify
    CRITICAL = "critical" # Block: auto-deny + alert


class ActionType(Enum):
    # Low risk actions
    QUERY = "query"
    LIGHT_CONTROL = "light_control"
    TEMPERATURE_READ = "temperature_read"
    
    # Medium risk actions
    THERMOSTAT_SET = "thermostat_set"
    CAMERA_VIEW = "camera_view"
    GUEST_ADD = "guest_add"
    
    # High risk actions
    DOOR_UNLOCK = "door_unlock"
    ALARM_CONTROL = "alarm_control"
    ADMIN_ACTION = "admin_action"
    
    # Critical risk actions
    SECURITY_DISABLE = "security_disable"
    MASTER_RESET = "master_reset"
    DATA_EXPORT = "data_export"


# Base security risk scores (0-100)
SECURITY_RISK_SCORES: Dict[ActionType, int] = {
    ActionType.QUERY: 5,
    ActionType.LIGHT_CONTROL: 10,
    ActionType.TEMPERATURE_READ: 5,
    ActionType.THERMOSTAT_SET: 25,
    ActionType.CAMERA_VIEW: 40,
    ActionType.GUEST_ADD: 35,
    ActionType.DOOR_UNLOCK: 80,
    ActionType.ALARM_CONTROL: 90,
    ActionType.ADMIN_ACTION: 70,
    ActionType.SECURITY_DISABLE: 100,
    ActionType.MASTER_RESET: 100,
    ActionType.DATA_EXPORT: 85,
}


@dataclass
class UserContext:
    """Context about the user making a request"""
    user_id: str
    role: str  # admin, resident, guest
    device_id: str
    ip_address: str
    session_duration: timedelta = field(default_factory=lambda: timedelta(0))
    request_count_last_hour: int = 0
    is_known_device: bool = False
    voice_verified: bool = False


@dataclass
class ActionRequest:
    """Represents an action request to be evaluated"""
    action_type: ActionType
    target: str  # e.g., "front_door", "living_room_light"
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BehaviorHistory:
    """Historical behavior patterns for a user"""
    user_id: str
    typical_hours: List[int] = field(default_factory=lambda: list(range(6, 23)))  # 6am-11pm
    typical_actions: Dict[str, int] = field(default_factory=dict)  # action -> count
    typical_devices: List[str] = field(default_factory=list)
    last_action_time: Optional[datetime] = None
    anomaly_count_24h: int = 0


@dataclass
class EnergyResult:
    """Result of energy calculation"""
    total_energy: float
    level: EnergyLevel
    security_risk: float
    behavior_surprise: float
    resource_cost: float
    recommended_action: str
    requires_verification: bool
    notify_admin: bool
    details: Dict[str, Any] = field(default_factory=dict)


class EnergyModel:
    """
    Thermodynamic energy model for action security evaluation.
    
    This model treats the system as moving through an energy landscape,
    where higher energy states require more verification/authorization.
    """
    
    def __init__(
        self,
        alpha: float = 0.5,  # Weight for security risk
        beta: float = 0.3,   # Weight for behavior surprise
        gamma: float = 0.2,  # Weight for resource cost
        threshold_low: float = 20.0,
        threshold_medium: float = 50.0,
        threshold_high: float = 80.0
    ):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.threshold_low = threshold_low
        self.threshold_medium = threshold_medium
        self.threshold_high = threshold_high
        
        # In-memory behavior history (replace with DB in production)
        self._behavior_history: Dict[str, BehaviorHistory] = {}
    
    def calculate_energy(
        self,
        action: ActionRequest,
        user: UserContext,
        plan_complexity: int = 1  # Number of tool calls in plan
    ) -> EnergyResult:
        """
        Calculate total energy for an action request.
        
        Args:
            action: The requested action
            user: Context about the requesting user
            plan_complexity: Number of LLM/tool calls needed
            
        Returns:
            EnergyResult with score, level, and recommended actions
        """
        # Calculate component scores (0-100 each)
        security_risk = self._calculate_security_risk(action, user)
        behavior_surprise = self._calculate_behavior_surprise(action, user)
        resource_cost = self._calculate_resource_cost(plan_complexity)
        
        # Weighted sum
        total_energy = (
            self.alpha * security_risk +
            self.beta * behavior_surprise +
            self.gamma * resource_cost
        )
        
        # Determine energy level
        level = self._determine_level(total_energy)
        
        # Determine recommended actions
        recommended_action, requires_verification, notify_admin = self._get_recommendations(level)
        
        return EnergyResult(
            total_energy=round(total_energy, 2),
            level=level,
            security_risk=round(security_risk, 2),
            behavior_surprise=round(behavior_surprise, 2),
            resource_cost=round(resource_cost, 2),
            recommended_action=recommended_action,
            requires_verification=requires_verification,
            notify_admin=notify_admin,
            details={
                "action_type": action.action_type.value,
                "user_role": user.role,
                "is_known_device": user.is_known_device,
                "voice_verified": user.voice_verified,
                "hour": action.timestamp.hour,
                "plan_complexity": plan_complexity
            }
        )
    
    def _calculate_security_risk(self, action: ActionRequest, user: UserContext) -> float:
        """Calculate security risk score (0-100)"""
        
        # Base risk from action type
        base_risk = SECURITY_RISK_SCORES.get(action.action_type, 50)
        
        # Role-based modifiers
        role_multipliers = {
            "admin": 0.5,     # Admins get lower risk scores
            "resident": 0.8,   # Residents get slight discount
            "guest": 1.5       # Guests get higher risk scores
        }
        role_mult = role_multipliers.get(user.role, 1.0)
        
        # Device familiarity modifier
        device_mult = 0.8 if user.is_known_device else 1.3
        
        # Voice verification modifier
        voice_mult = 0.6 if user.voice_verified else 1.0
        
        # Time of day modifier (late night = higher risk)
        hour = action.timestamp.hour
        if 23 <= hour or hour < 5:
            time_mult = 1.4  # Late night
        elif 5 <= hour < 7:
            time_mult = 1.2  # Early morning
        else:
            time_mult = 1.0  # Normal hours
        
        # Calculate final risk
        risk = base_risk * role_mult * device_mult * voice_mult * time_mult
        
        return min(100, max(0, risk))
    
    def _calculate_behavior_surprise(self, action: ActionRequest, user: UserContext) -> float:
        """Calculate behavior surprise score (0-100)"""
        
        history = self._get_or_create_history(user.user_id)
        surprise = 0.0
        
        # Unusual hour?
        hour = action.timestamp.hour
        if hour not in history.typical_hours:
            surprise += 30.0
        
        # Unknown device?
        if user.device_id not in history.typical_devices:
            surprise += 25.0
        
        # Unusual action frequency?
        action_key = f"{action.action_type.value}:{action.target}"
        typical_count = history.typical_actions.get(action_key, 0)
        if typical_count == 0:
            surprise += 20.0  # Never done this before
        
        # Recent anomalies?
        if history.anomaly_count_24h > 0:
            surprise += min(25.0, history.anomaly_count_24h * 5)
        
        # Rapid-fire requests?
        if user.request_count_last_hour > 50:
            surprise += 20.0
        
        return min(100, surprise)
    
    def _calculate_resource_cost(self, plan_complexity: int) -> float:
        """Calculate resource cost score (0-100)"""
        
        # Base cost per tool/LLM call
        base_cost_per_call = 10.0
        
        # Complexity multiplier
        cost = plan_complexity * base_cost_per_call
        
        # Cap at 100
        return min(100, cost)
    
    def _determine_level(self, energy: float) -> EnergyLevel:
        """Determine energy level from score"""
        if energy < self.threshold_low:
            return EnergyLevel.LOW
        elif energy < self.threshold_medium:
            return EnergyLevel.MEDIUM
        elif energy < self.threshold_high:
            return EnergyLevel.HIGH
        else:
            return EnergyLevel.CRITICAL
    
    def _get_recommendations(self, level: EnergyLevel) -> tuple:
        """Get recommended actions for energy level"""
        recommendations = {
            EnergyLevel.LOW: ("execute", False, False),
            EnergyLevel.MEDIUM: ("confirm", False, False),
            EnergyLevel.HIGH: ("verify_and_notify", True, True),
            EnergyLevel.CRITICAL: ("deny_and_alert", True, True)
        }
        return recommendations.get(level, ("deny", True, True))
    
    def _get_or_create_history(self, user_id: str) -> BehaviorHistory:
        """Get or create behavior history for a user"""
        if user_id not in self._behavior_history:
            self._behavior_history[user_id] = BehaviorHistory(user_id=user_id)
        return self._behavior_history[user_id]
    
    def record_action(self, action: ActionRequest, user: UserContext, was_anomaly: bool = False):
        """Record an action to update behavior history"""
        history = self._get_or_create_history(user.user_id)
        
        # Update typical actions
        action_key = f"{action.action_type.value}:{action.target}"
        history.typical_actions[action_key] = history.typical_actions.get(action_key, 0) + 1
        
        # Update typical devices
        if user.device_id not in history.typical_devices:
            history.typical_devices.append(user.device_id)
        
        # Update typical hours
        hour = action.timestamp.hour
        if hour not in history.typical_hours and not was_anomaly:
            history.typical_hours.append(hour)
        
        # Update anomaly count
        if was_anomaly:
            history.anomaly_count_24h += 1
        
        history.last_action_time = action.timestamp
    
    def decay_anomaly_count(self, user_id: str, decay_amount: int = 1):
        """Decay anomaly count over time (call periodically)"""
        if user_id in self._behavior_history:
            history = self._behavior_history[user_id]
            history.anomaly_count_24h = max(0, history.anomaly_count_24h - decay_amount)
    
    # F4.3.7: Voice verification trigger
    def should_trigger_voice_verification(self, result: EnergyResult) -> bool:
        """
        Determine if voice verification should be triggered.
        Triggered for HIGH energy actions or specific action types.
        """
        # Always require for HIGH or CRITICAL
        if result.level in [EnergyLevel.HIGH, EnergyLevel.CRITICAL]:
            return True
        
        # Require for specific high-risk actions even at medium energy
        high_risk_actions = ["door_unlock", "alarm_control", "admin_action", "security_disable"]
        if result.details.get("action_type") in high_risk_actions and result.level == EnergyLevel.MEDIUM:
            return True
        
        return False
    
    # F4.3.8: Admin notification
    async def notify_admin(
        self, 
        result: EnergyResult, 
        user_context: UserContext,
        action: ActionRequest
    ) -> bool:
        """
        Send notification to admin for high-energy actions.
        In production, integrate with email/SMS/push notification service.
        """
        if not result.notify_admin:
            return False
        
        notification = {
            "type": "security_alert",
            "severity": result.level.value,
            "timestamp": datetime.now().isoformat(),
            "energy_score": result.total_energy,
            "action": {
                "type": action.action_type.value,
                "target": action.target,
            },
            "user": {
                "id": user_context.user_id,
                "role": user_context.role,
                "device": user_context.device_id,
                "ip": user_context.ip_address,
                "voice_verified": user_context.voice_verified,
            },
            "recommendation": result.recommended_action,
        }
        
        # Log the notification
        logger.warning(f"ADMIN NOTIFICATION: {json.dumps(notification)}")
        
        # Add to audit log
        self.add_audit_log_entry(result, user_context, action, "admin_notified")
        
        # Send push notification via notification service
        try:
            from .notifications import get_notification_service
            notification_service = get_notification_service()
            
            # Fire and forget - don't block energy evaluation
            import asyncio
            asyncio.create_task(
                notification_service.notify_security_event(
                    level=result.level.value.upper(),
                    action=action.action_type.value,
                    user_id=user_context.user_id,
                    details={
                        "energy": result.total_energy,
                        "target": action.target,
                        "recommendation": result.recommended_action
                    }
                )
            )
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
        
        return True


# F4.3.9: Energy audit log
@dataclass
class AuditLogEntry:
    """A single entry in the energy audit log"""
    id: str
    timestamp: datetime
    user_id: str
    user_role: str
    action_type: str
    target: str
    energy_score: float
    energy_level: str
    was_allowed: bool
    verification_method: Optional[str] = None  # "voice", "pin", "none"
    admin_notified: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class EnergyAuditLog:
    """
    Audit log for all energy-evaluated actions.
    F4.3.9: Creates a persistent log of all security-relevant actions.
    """
    
    def __init__(self, max_entries: int = 10000):
        self._entries: List[AuditLogEntry] = []
        self._max_entries = max_entries
    
    def add_entry(
        self,
        result: EnergyResult,
        user: UserContext,
        action: ActionRequest,
        was_allowed: bool,
        verification_method: Optional[str] = None
    ) -> AuditLogEntry:
        """Add an entry to the audit log"""
        entry = AuditLogEntry(
            id=hashlib.md5(
                f"{datetime.now().isoformat()}{user.user_id}{action.target}".encode()
            ).hexdigest()[:12],
            timestamp=datetime.now(),
            user_id=user.user_id,
            user_role=user.role,
            action_type=action.action_type.value,
            target=action.target,
            energy_score=result.total_energy,
            energy_level=result.level.value,
            was_allowed=was_allowed,
            verification_method=verification_method,
            admin_notified=result.notify_admin,
            details={
                "device_id": user.device_id,
                "ip_address": user.ip_address,
                "security_risk": result.security_risk,
                "behavior_surprise": result.behavior_surprise,
                "resource_cost": result.resource_cost,
            }
        )
        
        self._entries.append(entry)
        
        # Trim if too large
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        
        logger.info(f"Audit log: {entry.action_type} on {entry.target} "
                   f"(E={entry.energy_score}, allowed={entry.was_allowed})")
        
        return entry
    
    def get_entries(
        self,
        limit: int = 100,
        user_id: Optional[str] = None,
        energy_level: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[AuditLogEntry]:
        """Get audit log entries with optional filtering"""
        entries = self._entries
        
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        
        if energy_level:
            entries = [e for e in entries if e.energy_level == energy_level]
        
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        
        return entries[-limit:]
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get statistics for the energy audit log"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [e for e in self._entries if e.timestamp >= cutoff]
        
        if not recent:
            return {
                "period_hours": hours,
                "total_actions": 0,
                "by_level": {},
                "blocked_actions": 0,
                "admin_notifications": 0,
            }
        
        by_level = {}
        for level in EnergyLevel:
            by_level[level.value] = len([e for e in recent if e.energy_level == level.value])
        
        return {
            "period_hours": hours,
            "total_actions": len(recent),
            "by_level": by_level,
            "blocked_actions": len([e for e in recent if not e.was_allowed]),
            "admin_notifications": len([e for e in recent if e.admin_notified]),
            "avg_energy": sum(e.energy_score for e in recent) / len(recent),
            "unique_users": len(set(e.user_id for e in recent)),
        }
    
    def export_json(self, limit: int = 1000) -> str:
        """Export audit log as JSON"""
        entries = self._entries[-limit:]
        return json.dumps([
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "user_id": e.user_id,
                "user_role": e.user_role,
                "action_type": e.action_type,
                "target": e.target,
                "energy_score": e.energy_score,
                "energy_level": e.energy_level,
                "was_allowed": e.was_allowed,
                "verification_method": e.verification_method,
                "admin_notified": e.admin_notified,
            }
            for e in entries
        ], indent=2)


# F4.3.10: Energy dashboard data
@dataclass
class EnergyDashboardData:
    """Data structure for energy dashboard visualization"""
    current_system_energy: float
    energy_trend: List[Dict[str, Any]]  # Time series
    action_distribution: Dict[str, int]  # By energy level
    high_risk_users: List[Dict[str, Any]]
    recent_alerts: List[Dict[str, Any]]
    statistics: Dict[str, Any]


class EnergyDashboard:
    """
    F4.3.10: Energy dashboard visualization data provider.
    Aggregates data from the energy model and audit log for UI display.
    """
    
    def __init__(self, audit_log: EnergyAuditLog, energy_model: 'EnergyModel'):
        self._audit_log = audit_log
        self._energy_model = energy_model
        self._energy_history: List[Dict[str, Any]] = []
    
    def record_energy_sample(self, energy: float):
        """Record a point-in-time energy sample for trend tracking"""
        self._energy_history.append({
            "timestamp": datetime.now().isoformat(),
            "energy": energy
        })
        # Keep last 1000 samples
        if len(self._energy_history) > 1000:
            self._energy_history = self._energy_history[-1000:]
    
    def get_dashboard_data(self) -> EnergyDashboardData:
        """Get comprehensive dashboard data"""
        stats = self._audit_log.get_statistics(24)
        recent = self._audit_log.get_entries(limit=100)
        
        # Calculate current system energy (average of recent actions)
        recent_energy = [e.energy_score for e in recent[-10:]] if recent else [0]
        current_energy = sum(recent_energy) / len(recent_energy)
        
        # Get high-risk users (users with HIGH/CRITICAL actions)
        high_risk_users = {}
        for entry in recent:
            if entry.energy_level in ["high", "critical"]:
                if entry.user_id not in high_risk_users:
                    high_risk_users[entry.user_id] = {
                        "user_id": entry.user_id,
                        "role": entry.user_role,
                        "high_energy_actions": 0,
                        "last_action": entry.timestamp.isoformat(),
                    }
                high_risk_users[entry.user_id]["high_energy_actions"] += 1
        
        # Get recent alerts (admin notifications)
        alerts = [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "action": e.action_type,
                "target": e.target,
                "user": e.user_id,
                "energy": e.energy_score,
            }
            for e in recent if e.admin_notified
        ][-10:]  # Last 10 alerts
        
        return EnergyDashboardData(
            current_system_energy=round(current_energy, 2),
            energy_trend=self._energy_history[-50:],  # Last 50 samples
            action_distribution=stats.get("by_level", {}),
            high_risk_users=list(high_risk_users.values()),
            recent_alerts=alerts,
            statistics=stats
        )
    
    def get_energy_level_color(self, energy: float) -> str:
        """Get CSS color for energy level"""
        if energy < 20:
            return "#00ff00"  # Green
        elif energy < 50:
            return "#ffff00"  # Yellow
        elif energy < 80:
            return "#ff9900"  # Orange
        else:
            return "#ff3333"  # Red


# Global instances
_energy_model: Optional[EnergyModel] = None
_audit_log: Optional[EnergyAuditLog] = None
_dashboard: Optional[EnergyDashboard] = None


def get_energy_model() -> EnergyModel:
    """Get or create the singleton energy model"""
    global _energy_model
    if _energy_model is None:
        _energy_model = EnergyModel()
    return _energy_model


def get_audit_log() -> EnergyAuditLog:
    """Get or create the singleton audit log"""
    global _audit_log
    if _audit_log is None:
        _audit_log = EnergyAuditLog()
    return _audit_log


def get_dashboard() -> EnergyDashboard:
    """Get or create the singleton dashboard"""
    global _dashboard
    if _dashboard is None:
        _dashboard = EnergyDashboard(get_audit_log(), get_energy_model())
    return _dashboard


# Add method to EnergyModel for audit logging
def _add_audit_log_entry_to_model(self, result, user, action, status):
    """Add entry to audit log from model"""
    audit_log = get_audit_log()
    was_allowed = status != "denied"
    verification = "voice" if user.voice_verified else None
    audit_log.add_entry(result, user, action, was_allowed, verification)

# Monkey-patch the method onto EnergyModel
EnergyModel.add_audit_log_entry = _add_audit_log_entry_to_model


# Helper function for common use case
async def evaluate_action(
    action_type: str,
    target: str,
    user_id: str,
    user_role: str,
    device_id: str,
    ip_address: str,
    **kwargs
) -> EnergyResult:
    """
    Convenient function to evaluate an action's energy level.
    
    Example:
        result = await evaluate_action(
            action_type="door_unlock",
            target="front_door",
            user_id="user123",
            user_role="guest",
            device_id="iphone_x_abc",
            ip_address="192.168.1.100"
        )
        
        if result.level == EnergyLevel.CRITICAL:
            return {"error": "Action denied", "reason": "Security risk too high"}
    """
    model = get_energy_model()
    
    # Parse action type
    try:
        action_enum = ActionType(action_type)
    except ValueError:
        action_enum = ActionType.QUERY  # Default to safe
    
    action = ActionRequest(
        action_type=action_enum,
        target=target,
        parameters=kwargs
    )
    
    user = UserContext(
        user_id=user_id,
        role=user_role,
        device_id=device_id,
        ip_address=ip_address,
        is_known_device=kwargs.get("is_known_device", False),
        voice_verified=kwargs.get("voice_verified", False)
    )
    
    plan_complexity = kwargs.get("plan_complexity", 1)
    
    return model.calculate_energy(action, user, plan_complexity)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_energy_model():
        # Test various scenarios
        scenarios = [
            # Low energy: Resident turns on light during day
            {
                "action_type": "light_control",
                "target": "living_room",
                "user_id": "resident1",
                "user_role": "resident",
                "device_id": "known_phone",
                "ip_address": "192.168.1.50",
                "is_known_device": True
            },
            # Medium energy: Guest asks about house rules
            {
                "action_type": "query",
                "target": "house_rules",
                "user_id": "guest1",
                "user_role": "guest",
                "device_id": "unknown_phone",
                "ip_address": "192.168.1.100"
            },
            # High energy: Guest tries to unlock door at 3am
            {
                "action_type": "door_unlock",
                "target": "front_door",
                "user_id": "guest1",
                "user_role": "guest",
                "device_id": "unknown_tablet",
                "ip_address": "192.168.1.101"
            },
            # Critical: Unknown user tries to disable security
            {
                "action_type": "security_disable",
                "target": "alarm_system",
                "user_id": "unknown",
                "user_role": "guest",
                "device_id": "unknown",
                "ip_address": "192.168.1.200"
            }
        ]
        
        for scenario in scenarios:
            result = await evaluate_action(**scenario)
            print(f"\n{'='*50}")
            print(f"Action: {scenario['action_type']} on {scenario['target']}")
            print(f"User: {scenario['user_role']} ({scenario['user_id']})")
            print(f"Energy: {result.total_energy} ({result.level.value})")
            print(f"  - Security Risk: {result.security_risk}")
            print(f"  - Behavior Surprise: {result.behavior_surprise}")
            print(f"  - Resource Cost: {result.resource_cost}")
            print(f"Recommendation: {result.recommended_action}")
            print(f"Requires Verification: {result.requires_verification}")
            print(f"Notify Admin: {result.notify_admin}")
    
    asyncio.run(test_energy_model())
