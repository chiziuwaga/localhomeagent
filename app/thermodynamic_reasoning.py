"""
Thermodynamic Reasoning Engine (P3/N1.2)

Inspired by Extropic's thermodynamic computing principles and applied
to AI agent security decision-making.

Core Concept:
The system models security decisions as movements through an energy landscape.
Low-energy states are "safe" (routine operations), while high-energy states
require more verification before transitioning.

Free Energy Principle (adapted from Friston's Active Inference):
The agent minimizes surprise by predicting user behavior and flagging
anomalies as high-energy states that need resolution.

Energy Landscape:
                    High Energy (Danger)
                    ▲
                    │     ╱╲
                    │    ╱  ╲    ← Critical: Block
                    │   ╱    ╲
                    │  ╱──────╲  ← High: Verify
                    │ ╱        ╲
                    │╱──────────╲← Medium: Confirm
                    ╱────────────╲
    Low Energy ────╱──────────────╲────▶ Safe: Execute
                  Time →

Components:
1. Energy Calculator: Computes system energy from multiple factors
2. Gradient Descent: Finds path to lower energy states
3. Transition Validator: Validates state transitions
4. Entropy Monitor: Tracks system disorder
"""

import logging
import math
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """Possible states in the energy landscape"""
    IDLE = "idle"           # Lowest energy, no activity
    ACTIVE = "active"       # Normal operations
    VIGILANT = "vigilant"   # Heightened awareness
    ALERT = "alert"         # Potential threat detected
    LOCKDOWN = "lockdown"   # Critical threat, block all


@dataclass
class EnergyFactors:
    """Factors that contribute to system energy"""
    security_risk: float = 0.0      # Risk of the action (0-100)
    behavior_surprise: float = 0.0   # How unexpected is this? (0-100)
    resource_cost: float = 0.0       # Computational/resource cost (0-100)
    temporal_anomaly: float = 0.0    # Time-based anomaly (0-100)
    entropy_level: float = 0.0       # System disorder (0-100)
    
    def total(self, weights: 'EnergyWeights') -> float:
        """Calculate weighted total energy"""
        return (
            weights.alpha * self.security_risk +
            weights.beta * self.behavior_surprise +
            weights.gamma * self.resource_cost +
            weights.delta * self.temporal_anomaly +
            weights.epsilon * self.entropy_level
        )


@dataclass
class EnergyWeights:
    """Weights for energy factors (must sum to 1.0)"""
    alpha: float = 0.35   # Security risk weight
    beta: float = 0.25    # Behavior surprise weight
    gamma: float = 0.15   # Resource cost weight
    delta: float = 0.15   # Temporal anomaly weight
    epsilon: float = 0.10 # Entropy weight
    
    def __post_init__(self):
        total = self.alpha + self.beta + self.gamma + self.delta + self.epsilon
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


@dataclass
class ThermodynamicState:
    """Current state of the thermodynamic system"""
    current_energy: float
    state: SystemState
    factors: EnergyFactors
    gradient: float  # Direction of energy change
    entropy: float
    temperature: float  # Affects transition probabilities
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StateTransition:
    """A transition between states"""
    from_state: SystemState
    to_state: SystemState
    energy_delta: float
    probability: float
    requires_verification: bool
    reasoning: str


class EntropyMonitor:
    """
    Monitors system entropy (disorder) over time.
    High entropy indicates unpredictable behavior patterns.
    """
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.observations: deque = deque(maxlen=window_size)
        self.baseline_entropy: Optional[float] = None
    
    def observe(self, value: float):
        """Record an observation"""
        self.observations.append(value)
    
    def calculate_entropy(self) -> float:
        """
        Calculate Shannon entropy of recent observations.
        Returns value between 0 (ordered) and 1 (chaotic).
        """
        if len(self.observations) < 10:
            return 0.5  # Not enough data
        
        # Discretize observations into bins
        obs_list = list(self.observations)
        min_val = min(obs_list)
        max_val = max(obs_list)
        
        if max_val == min_val:
            return 0.0  # All same value = no entropy
        
        # Create 10 bins
        n_bins = 10
        bin_size = (max_val - min_val) / n_bins
        bins = [0] * n_bins
        
        for val in obs_list:
            bin_idx = min(int((val - min_val) / bin_size), n_bins - 1)
            bins[bin_idx] += 1
        
        # Calculate entropy
        total = len(obs_list)
        entropy = 0.0
        for count in bins:
            if count > 0:
                prob = count / total
                entropy -= prob * math.log2(prob)
        
        # Normalize to 0-1
        max_entropy = math.log2(n_bins)
        return entropy / max_entropy if max_entropy > 0 else 0
    
    def get_anomaly_score(self) -> float:
        """
        Get anomaly score based on entropy deviation from baseline.
        Returns 0-100 scale.
        """
        current_entropy = self.calculate_entropy()
        
        if self.baseline_entropy is None:
            self.baseline_entropy = current_entropy
            return 0.0
        
        deviation = abs(current_entropy - self.baseline_entropy)
        
        # Slowly adapt baseline
        self.baseline_entropy = 0.95 * self.baseline_entropy + 0.05 * current_entropy
        
        # Convert deviation to 0-100 scale
        return min(100, deviation * 200)


class TemperatureController:
    """
    Controls system "temperature" which affects transition probabilities.
    Higher temperature = more willing to take risks (explore).
    Lower temperature = more conservative (exploit known safe states).
    """
    
    def __init__(
        self,
        initial_temp: float = 1.0,
        min_temp: float = 0.1,
        max_temp: float = 3.0,
    ):
        self.temperature = initial_temp
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.history: deque = deque(maxlen=50)
    
    def adjust(self, success: bool, energy_level: float):
        """
        Adjust temperature based on outcomes.
        
        Success at high energy → increase temperature (more bold)
        Failure at any level → decrease temperature (more cautious)
        """
        if success:
            # Increase temp proportionally to energy level
            delta = 0.1 * (energy_level / 100)
            self.temperature = min(self.max_temp, self.temperature + delta)
        else:
            # Decrease temp
            self.temperature = max(self.min_temp, self.temperature * 0.9)
        
        self.history.append(self.temperature)
    
    def get_transition_probability(
        self,
        energy_delta: float,
        current_energy: float,
    ) -> float:
        """
        Calculate probability of accepting a state transition.
        Based on Metropolis-Hastings acceptance criterion.
        
        P(accept) = min(1, exp(-ΔE / T))
        
        For downhill (energy decrease): always accept
        For uphill (energy increase): probabilistically accept based on T
        """
        if energy_delta <= 0:
            return 1.0  # Always accept downhill transitions
        
        # Boltzmann factor for uphill transitions
        prob = math.exp(-energy_delta / (self.temperature * 50))
        return min(1.0, prob)


class ThermodynamicReasoner:
    """
    Main thermodynamic reasoning engine.
    Uses energy-based reasoning to make security decisions.
    """
    
    # State thresholds
    STATE_THRESHOLDS = {
        SystemState.IDLE: 10.0,
        SystemState.ACTIVE: 30.0,
        SystemState.VIGILANT: 50.0,
        SystemState.ALERT: 75.0,
        SystemState.LOCKDOWN: 100.0,
    }
    
    def __init__(
        self,
        weights: Optional[EnergyWeights] = None,
        initial_state: SystemState = SystemState.IDLE,
    ):
        self.weights = weights or EnergyWeights()
        self.current_state = initial_state
        self.entropy_monitor = EntropyMonitor()
        self.temperature = TemperatureController()
        
        # Energy history for gradient calculation
        self.energy_history: deque = deque(maxlen=10)
        self.current_energy = 0.0
        
        # State transition log
        self.transition_log: List[StateTransition] = []
    
    def calculate_energy(
        self,
        security_risk: float,
        behavior_surprise: float,
        resource_cost: float,
        temporal_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, EnergyFactors]:
        """
        Calculate total system energy from factors.
        
        Args:
            security_risk: Risk score of the action (0-100)
            behavior_surprise: How unexpected is this (0-100)
            resource_cost: Computational cost (0-100)
            temporal_context: Optional time-based context
            
        Returns:
            Tuple of (total_energy, factors)
        """
        # Calculate temporal anomaly
        temporal_anomaly = 0.0
        if temporal_context:
            hour = temporal_context.get("hour", datetime.now().hour)
            # Late night = higher anomaly
            if 0 <= hour < 6:
                temporal_anomaly = 40.0
            elif 22 <= hour <= 23:
                temporal_anomaly = 20.0
            
            # Rapid requests = higher anomaly
            request_rate = temporal_context.get("request_rate", 0)
            if request_rate > 10:
                temporal_anomaly += min(30, request_rate * 2)
        
        # Get current entropy level
        self.entropy_monitor.observe(security_risk)
        entropy_level = self.entropy_monitor.get_anomaly_score()
        
        factors = EnergyFactors(
            security_risk=security_risk,
            behavior_surprise=behavior_surprise,
            resource_cost=resource_cost,
            temporal_anomaly=temporal_anomaly,
            entropy_level=entropy_level,
        )
        
        total_energy = factors.total(self.weights)
        
        # Update history
        self.energy_history.append(total_energy)
        self.current_energy = total_energy
        
        return total_energy, factors
    
    def get_gradient(self) -> float:
        """
        Calculate energy gradient (direction of change).
        Positive = energy increasing (getting riskier)
        Negative = energy decreasing (getting safer)
        """
        if len(self.energy_history) < 2:
            return 0.0
        
        history = list(self.energy_history)
        recent = statistics.mean(history[-3:]) if len(history) >= 3 else history[-1]
        older = statistics.mean(history[:-3]) if len(history) > 3 else history[0]
        
        return recent - older
    
    def determine_state(self, energy: float) -> SystemState:
        """Determine system state from energy level"""
        for state in reversed(list(SystemState)):
            threshold = self.STATE_THRESHOLDS[state]
            if energy >= threshold:
                return state
        return SystemState.IDLE
    
    def evaluate_transition(
        self,
        target_state: SystemState,
        action_description: str,
    ) -> StateTransition:
        """
        Evaluate whether a state transition should be allowed.
        
        Uses thermodynamic principles:
        - Downhill transitions (to lower energy) are always allowed
        - Uphill transitions are probabilistically allowed based on temperature
        """
        current_threshold = self.STATE_THRESHOLDS[self.current_state]
        target_threshold = self.STATE_THRESHOLDS[target_state]
        energy_delta = target_threshold - current_threshold
        
        # Calculate transition probability
        prob = self.temperature.get_transition_probability(
            energy_delta,
            self.current_energy,
        )
        
        # Determine if verification is required
        requires_verification = False
        if target_state in [SystemState.ALERT, SystemState.LOCKDOWN]:
            requires_verification = True
        elif energy_delta > 20:
            requires_verification = True
        
        reasoning = f"Transition from {self.current_state.value} to {target_state.value}: "
        reasoning += f"ΔE={energy_delta:.1f}, P(accept)={prob:.2f}. "
        
        if energy_delta <= 0:
            reasoning += "Downhill transition, always allowed."
        else:
            reasoning += f"Uphill transition, T={self.temperature.temperature:.2f}."
        
        return StateTransition(
            from_state=self.current_state,
            to_state=target_state,
            energy_delta=energy_delta,
            probability=prob,
            requires_verification=requires_verification,
            reasoning=reasoning,
        )
    
    def apply_transition(
        self,
        transition: StateTransition,
        force: bool = False,
    ) -> bool:
        """
        Apply a state transition.
        
        Returns True if transition was applied, False if rejected.
        """
        if force or transition.probability >= 0.5:
            self.current_state = transition.to_state
            self.transition_log.append(transition)
            
            # Keep only last 100 transitions
            if len(self.transition_log) > 100:
                self.transition_log = self.transition_log[-100:]
            
            return True
        
        return False
    
    def reason(
        self,
        action_type: str,
        security_risk: float,
        behavior_surprise: float,
        resource_cost: float,
        temporal_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform thermodynamic reasoning about an action.
        
        This is the main entry point for reasoning about security decisions.
        
        Returns:
            Dict with reasoning results, recommended action, and explanation
        """
        # Calculate energy
        total_energy, factors = self.calculate_energy(
            security_risk=security_risk,
            behavior_surprise=behavior_surprise,
            resource_cost=resource_cost,
            temporal_context=temporal_context,
        )
        
        # Determine target state
        target_state = self.determine_state(total_energy)
        
        # Evaluate transition
        transition = self.evaluate_transition(target_state, action_type)
        
        # Get gradient
        gradient = self.get_gradient()
        
        # Build thermodynamic state
        thermo_state = ThermodynamicState(
            current_energy=total_energy,
            state=target_state,
            factors=factors,
            gradient=gradient,
            entropy=self.entropy_monitor.calculate_entropy(),
            temperature=self.temperature.temperature,
        )
        
        # Determine recommendation
        if target_state == SystemState.LOCKDOWN:
            recommendation = "BLOCK"
            explanation = "Energy level critical. Action blocked for security."
        elif target_state == SystemState.ALERT:
            recommendation = "VERIFY"
            explanation = "High energy state. Additional verification required."
        elif target_state == SystemState.VIGILANT:
            recommendation = "CONFIRM"
            explanation = "Elevated energy. User confirmation recommended."
        elif gradient > 10:
            recommendation = "MONITOR"
            explanation = "Energy rising rapidly. Monitoring for anomalies."
        else:
            recommendation = "ALLOW"
            explanation = "Energy within safe bounds. Proceeding."
        
        return {
            "recommendation": recommendation,
            "explanation": explanation,
            "energy": {
                "total": total_energy,
                "factors": {
                    "security_risk": factors.security_risk,
                    "behavior_surprise": factors.behavior_surprise,
                    "resource_cost": factors.resource_cost,
                    "temporal_anomaly": factors.temporal_anomaly,
                    "entropy_level": factors.entropy_level,
                },
                "gradient": gradient,
            },
            "state": {
                "current": self.current_state.value,
                "target": target_state.value,
                "temperature": self.temperature.temperature,
                "entropy": thermo_state.entropy,
            },
            "transition": {
                "from": transition.from_state.value,
                "to": transition.to_state.value,
                "energy_delta": transition.energy_delta,
                "probability": transition.probability,
                "requires_verification": transition.requires_verification,
                "reasoning": transition.reasoning,
            },
        }
    
    def feedback(self, action_allowed: bool, success: bool):
        """
        Provide feedback on action outcome to adjust temperature.
        
        Args:
            action_allowed: Was the action allowed?
            success: Was the outcome successful (no security incident)?
        """
        if action_allowed:
            self.temperature.adjust(success, self.current_energy)
        
        # If action was allowed but failed, immediately lower temperature
        if action_allowed and not success:
            self.current_state = SystemState.ALERT
            self.temperature.temperature = max(
                self.temperature.min_temp,
                self.temperature.temperature * 0.5,
            )


# Integration with existing energy model
def integrate_with_energy_model(reasoner: ThermodynamicReasoner):
    """
    Create wrapper functions to integrate with existing EnergyModel.
    """
    from .energy_model import EnergyModel, EnergyResult
    
    def enhanced_evaluate(
        energy_model: EnergyModel,
        action,
        user,
        plan_complexity: int = 1,
    ) -> Tuple[EnergyResult, Dict[str, Any]]:
        """
        Enhanced evaluation that combines EnergyModel with thermodynamic reasoning.
        """
        # Get base result from energy model
        result = energy_model.calculate_energy(action, user, plan_complexity)
        
        # Get thermodynamic reasoning
        thermo_result = reasoner.reason(
            action_type=action.action_type.value,
            security_risk=result.security_risk,
            behavior_surprise=result.behavior_surprise,
            resource_cost=result.resource_cost,
            temporal_context={
                "hour": action.timestamp.hour,
                "request_rate": user.request_count_last_hour,
            },
        )
        
        return result, thermo_result
    
    return enhanced_evaluate


__all__ = [
    "ThermodynamicReasoner",
    "ThermodynamicState",
    "SystemState",
    "EnergyFactors",
    "EnergyWeights",
    "EntropyMonitor",
    "TemperatureController",
    "integrate_with_energy_model",
]
