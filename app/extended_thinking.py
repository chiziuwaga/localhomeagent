"""
Extended Thinking Modes Module
P5: TH1 - Gradient thinking depths for AI capability

Features:
- TH1.1: ThinkingMode enum (QUICK, STANDARD, DEEP, RECURSIVE)
- TH1.2: Thinking mode selector support
- TH1.3: QUICK mode (~500ms)
- TH1.4: STANDARD mode (current)
- TH1.5: DEEP mode (multi-paragraph)
- TH1.6: RECURSIVE mode (self-correcting)
- TH1.7: Mode indicators
- TH1.8: Energy cost scaling
- TH1.9: Thinking budget display
- TH1.10: Automatic mode escalation
- TH1.11: Context-aware token budget scaling (integrates with context_manager)
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Callable, AsyncGenerator, TYPE_CHECKING
from pydantic import BaseModel

# Conditional import to avoid circular dependencies
if TYPE_CHECKING:
    from context_manager import ContextManager, TokenBudget as ContextTokenBudget

logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS
# ============================================================================

class ThinkingMode(str, Enum):
    """Available thinking modes with increasing depth"""
    QUICK = "quick"         # Fast, surface-level (< 500ms)
    STANDARD = "standard"   # Normal thinking (1-5s)
    DEEP = "deep"           # Thorough analysis (5-30s)
    RECURSIVE = "recursive" # Self-correcting loops (30s+)


class ThinkingPhase(str, Enum):
    """Phases within a thinking process"""
    UNDERSTANDING = "understanding"
    ANALYZING = "analyzing"
    REASONING = "reasoning"
    SYNTHESIZING = "synthesizing"
    VALIDATING = "validating"
    REFINING = "refining"


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ThinkingModeConfig:
    """Configuration for each thinking mode"""
    mode: ThinkingMode
    max_tokens: int
    temperature: float
    energy_cost: int
    timeout_seconds: float
    phases: List[ThinkingPhase]
    max_iterations: int = 1
    require_validation: bool = False
    
    @staticmethod
    def get_config(mode: ThinkingMode) -> "ThinkingModeConfig":
        configs = {
            ThinkingMode.QUICK: ThinkingModeConfig(
                mode=ThinkingMode.QUICK,
                max_tokens=150,
                temperature=0.3,
                energy_cost=5,
                timeout_seconds=2.0,
                phases=[ThinkingPhase.UNDERSTANDING],
                max_iterations=1,
                require_validation=False
            ),
            ThinkingMode.STANDARD: ThinkingModeConfig(
                mode=ThinkingMode.STANDARD,
                max_tokens=500,
                temperature=0.5,
                energy_cost=15,
                timeout_seconds=10.0,
                phases=[ThinkingPhase.UNDERSTANDING, ThinkingPhase.REASONING],
                max_iterations=1,
                require_validation=False
            ),
            ThinkingMode.DEEP: ThinkingModeConfig(
                mode=ThinkingMode.DEEP,
                max_tokens=2000,
                temperature=0.7,
                energy_cost=35,
                timeout_seconds=60.0,
                phases=[
                    ThinkingPhase.UNDERSTANDING,
                    ThinkingPhase.ANALYZING,
                    ThinkingPhase.REASONING,
                    ThinkingPhase.SYNTHESIZING
                ],
                max_iterations=1,
                require_validation=True
            ),
            ThinkingMode.RECURSIVE: ThinkingModeConfig(
                mode=ThinkingMode.RECURSIVE,
                max_tokens=4000,
                temperature=0.8,
                energy_cost=60,
                timeout_seconds=180.0,
                phases=[
                    ThinkingPhase.UNDERSTANDING,
                    ThinkingPhase.ANALYZING,
                    ThinkingPhase.REASONING,
                    ThinkingPhase.SYNTHESIZING,
                    ThinkingPhase.VALIDATING,
                    ThinkingPhase.REFINING
                ],
                max_iterations=3,
                require_validation=True
            )
        }
        return configs[mode]
    
    def adjust_for_context_budget(self, available_tokens: int) -> "ThinkingModeConfig":
        """
        Adjust max_tokens based on available context window budget.
        
        Context-aware scaling for downstream agentic architecture:
        - If plenty of context available: use full max_tokens
        - If context constrained: scale down proportionally
        - Minimum 50 tokens for any mode to remain useful
        
        Args:
            available_tokens: Tokens available for thinking (from ContextManager.get_thinking_budget())
        
        Returns:
            New ThinkingModeConfig with adjusted max_tokens
        """
        # Keep at least 50 tokens for minimal response
        min_tokens = 50
        
        # If plenty of room, use full allocation
        if available_tokens >= self.max_tokens:
            return self
        
        # Calculate scaled tokens
        scaled_tokens = max(min_tokens, min(available_tokens, self.max_tokens))
        
        # Reduce phases if significantly constrained
        adjusted_phases = self.phases.copy()
        if scaled_tokens < self.max_tokens * 0.25:
            # Very constrained - only use first 2 phases
            adjusted_phases = self.phases[:min(2, len(self.phases))]
        elif scaled_tokens < self.max_tokens * 0.5:
            # Moderately constrained - use first 3 phases
            adjusted_phases = self.phases[:min(3, len(self.phases))]
        
        # Log the adjustment
        if scaled_tokens < self.max_tokens:
            logger.info(
                f"Context-aware adjustment: {self.mode.value} "
                f"{self.max_tokens} -> {scaled_tokens} tokens "
                f"({len(self.phases)} -> {len(adjusted_phases)} phases)"
            )
        
        return ThinkingModeConfig(
            mode=self.mode,
            max_tokens=scaled_tokens,
            temperature=self.temperature,
            energy_cost=self.energy_cost,
            timeout_seconds=self.timeout_seconds,
            phases=adjusted_phases,
            max_iterations=self.max_iterations,
            require_validation=self.require_validation
        )

    @staticmethod
    def get_recommended_mode_for_context(available_tokens: int) -> ThinkingMode:
        """
        Recommend a thinking mode based on available context.
        
        Use this when auto-selecting mode based on context constraints:
        - < 200 tokens: QUICK only
        - 200-600 tokens: STANDARD
        - 600-2500 tokens: DEEP possible
        - > 2500 tokens: RECURSIVE possible
        
        Args:
            available_tokens: Available tokens from context manager
        
        Returns:
            Recommended ThinkingMode
        """
        if available_tokens < 200:
            return ThinkingMode.QUICK
        elif available_tokens < 600:
            return ThinkingMode.STANDARD
        elif available_tokens < 2500:
            return ThinkingMode.DEEP
        else:
            return ThinkingMode.RECURSIVE


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ThinkingStep:
    """A single step in the thinking process"""
    phase: ThinkingPhase
    content: str
    duration_ms: float
    tokens_used: int
    confidence: float = 1.0
    needs_refinement: bool = False


@dataclass
class ThinkingResult:
    """Result of a thinking process"""
    mode: ThinkingMode
    query: str
    response: str
    thinking_steps: List[ThinkingStep]
    total_duration_ms: float
    total_tokens: int
    energy_consumed: int
    iterations: int
    final_confidence: float
    escalated_from: Optional[ThinkingMode] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "query": self.query,
            "response": self.response,
            "thinking_steps": [
                {
                    "phase": s.phase.value,
                    "content": s.content,
                    "duration_ms": s.duration_ms,
                    "tokens_used": s.tokens_used,
                    "confidence": s.confidence
                }
                for s in self.thinking_steps
            ],
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "energy_consumed": self.energy_consumed,
            "iterations": self.iterations,
            "final_confidence": self.final_confidence,
            "escalated_from": self.escalated_from.value if self.escalated_from else None
        }


@dataclass
class ThinkingBudget:
    """Energy budget for thinking"""
    total_energy: int = 100
    consumed_energy: int = 0
    reset_time: Optional[datetime] = None
    
    @property
    def remaining(self) -> int:
        return max(0, self.total_energy - self.consumed_energy)
    
    def can_afford(self, cost: int) -> bool:
        return self.remaining >= cost
    
    def consume(self, cost: int) -> bool:
        if not self.can_afford(cost):
            return False
        self.consumed_energy += cost
        return True
    
    def reset(self):
        self.consumed_energy = 0
        self.reset_time = datetime.now()


# ============================================================================
# THINKING ENGINE
# ============================================================================

class ExtendedThinkingEngine:
    """
    Engine for multi-mode thinking with automatic escalation.
    Integrates with the energy model for budget management.
    
    Now supports context-aware token budget management:
    - Dynamically adjusts thinking modes based on context window availability
    - Integrates with ContextManager for token tracking
    - Automatically scales down thinking depth when context is limited
    """
    
    def __init__(
        self,
        llm_client: Any = None,
        enable_auto_escalation: bool = True,
        confidence_threshold: float = 0.7,
        context_manager: Optional[Any] = None  # Optional ContextManager instance
    ):
        self.llm_client = llm_client
        self.enable_auto_escalation = enable_auto_escalation
        self.confidence_threshold = confidence_threshold
        self.context_manager = context_manager  # ContextManager for token tracking
        self.budgets: Dict[str, ThinkingBudget] = {}  # user_id -> budget
        
        # Metrics
        self.total_queries = 0
        self.mode_usage: Dict[ThinkingMode, int] = {m: 0 for m in ThinkingMode}
        self.escalations = 0
        self.context_adjustments = 0  # Track how often context limits thinking
    
    def set_context_manager(self, context_manager: Any) -> None:
        """Set or update the context manager for token tracking"""
        self.context_manager = context_manager
    
    def get_available_thinking_tokens(self) -> Optional[int]:
        """
        Get available tokens for thinking from context manager.
        
        Returns:
            Number of available tokens, or None if no context manager
        """
        if self.context_manager is None:
            return None
        
        try:
            budget = self.context_manager.get_thinking_budget()
            return budget.available
        except Exception as e:
            logger.warning(f"Failed to get thinking budget from context manager: {e}")
            return None
    
    def get_budget(self, user_id: str) -> ThinkingBudget:
        """Get or create thinking budget for user"""
        if user_id not in self.budgets:
            self.budgets[user_id] = ThinkingBudget()
        
        budget = self.budgets[user_id]
        
        # Reset daily
        if budget.reset_time and (datetime.now() - budget.reset_time) > timedelta(hours=24):
            budget.reset()
        
        return budget
    
    async def think(
        self,
        query: str,
        mode: ThinkingMode = ThinkingMode.STANDARD,
        user_id: str = "default",
        context: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        respect_context_limits: bool = True  # Whether to adjust based on context window
    ) -> ThinkingResult:
        """
        Process a query with the specified thinking mode.
        May auto-escalate if confidence is low.
        
        Args:
            query: The query to process
            mode: Initial thinking mode
            user_id: User identifier for budget tracking
            context: Optional additional context
            stream: Whether to stream responses
            respect_context_limits: If True and context_manager exists, 
                                   adjust thinking based on available tokens
        """
        start_time = time.time()
        self.total_queries += 1
        
        # Get configuration
        config = ThinkingModeConfig.get_config(mode)
        budget = self.get_budget(user_id)
        
        # Check energy budget
        if not budget.can_afford(config.energy_cost):
            logger.warning(f"Insufficient thinking budget for {mode.value}")
            # Fall back to quick mode
            config = ThinkingModeConfig.get_config(ThinkingMode.QUICK)
        
        # Context-aware adjustment: scale thinking based on available context window
        if respect_context_limits:
            available_tokens = self.get_available_thinking_tokens()
            if available_tokens is not None:
                # Check if we should downgrade the mode entirely
                recommended_mode = ThinkingModeConfig.get_recommended_mode_for_context(available_tokens)
                if self._mode_priority(recommended_mode) < self._mode_priority(mode):
                    logger.info(
                        f"Context limits downgrade: {mode.value} -> {recommended_mode.value} "
                        f"(only {available_tokens} tokens available)"
                    )
                    mode = recommended_mode
                    config = ThinkingModeConfig.get_config(mode)
                    self.context_adjustments += 1
                
                # Adjust token allocation within the mode
                config = config.adjust_for_context_budget(available_tokens)
        
        # Execute thinking
        result = await self._execute_thinking(query, config, context)
        
        # Report token usage back to context manager
        if self.context_manager is not None:
            try:
                self.context_manager.add_message("assistant", result.response)
            except Exception as e:
                logger.warning(f"Failed to report usage to context manager: {e}")
        
        # Check for auto-escalation
        if (
            self.enable_auto_escalation and
            result.final_confidence < self.confidence_threshold and
            mode != ThinkingMode.RECURSIVE
        ):
            # Escalate to next level
            next_mode = self._get_next_mode(mode)
            next_config = ThinkingModeConfig.get_config(next_mode)
            
            if budget.can_afford(next_config.energy_cost):
                logger.info(f"Auto-escalating from {mode.value} to {next_mode.value}")
                self.escalations += 1
                escalated_result = await self._execute_thinking(query, next_config, context)
                escalated_result.escalated_from = mode
                result = escalated_result
        
        # Consume budget
        budget.consume(result.energy_consumed)
        
        # Update metrics
        self.mode_usage[result.mode] += 1
        
        result.total_duration_ms = (time.time() - start_time) * 1000
        return result
    
    async def _execute_thinking(
        self,
        query: str,
        config: ThinkingModeConfig,
        context: Optional[Dict[str, Any]]
    ) -> ThinkingResult:
        """Execute thinking with given configuration"""
        steps: List[ThinkingStep] = []
        total_tokens = 0
        iteration = 0
        final_response = ""
        
        for iteration in range(config.max_iterations):
            for phase in config.phases:
                step = await self._execute_phase(
                    query=query,
                    phase=phase,
                    config=config,
                    context=context,
                    previous_steps=steps
                )
                steps.append(step)
                total_tokens += step.tokens_used
                
                # Check if refinement needed
                if step.needs_refinement and iteration < config.max_iterations - 1:
                    break
            
            # Get final response after last phase
            if steps:
                final_response = steps[-1].content
                
                # Check confidence
                avg_confidence = sum(s.confidence for s in steps) / len(steps)
                if avg_confidence >= self.confidence_threshold:
                    break
        
        return ThinkingResult(
            mode=config.mode,
            query=query,
            response=final_response,
            thinking_steps=steps,
            total_duration_ms=0,  # Set by caller
            total_tokens=total_tokens,
            energy_consumed=config.energy_cost,
            iterations=iteration + 1,
            final_confidence=steps[-1].confidence if steps else 0
        )
    
    async def _execute_phase(
        self,
        query: str,
        phase: ThinkingPhase,
        config: ThinkingModeConfig,
        context: Optional[Dict[str, Any]],
        previous_steps: List[ThinkingStep]
    ) -> ThinkingStep:
        """Execute a single thinking phase"""
        start_time = time.time()
        
        # Build phase-specific prompt
        prompt = self._build_phase_prompt(query, phase, previous_steps, context)
        
        # Call LLM (or simulate if no client)
        if self.llm_client:
            response = await self._call_llm(prompt, config)
        else:
            response = await self._simulate_response(query, phase, config)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Estimate tokens (rough: 4 chars per token)
        tokens_used = len(response) // 4
        
        # Assess confidence based on phase
        confidence = self._assess_confidence(response, phase)
        
        return ThinkingStep(
            phase=phase,
            content=response,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            confidence=confidence,
            needs_refinement=confidence < self.confidence_threshold
        )
    
    def _build_phase_prompt(
        self,
        query: str,
        phase: ThinkingPhase,
        previous_steps: List[ThinkingStep],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for specific thinking phase"""
        phase_instructions = {
            ThinkingPhase.UNDERSTANDING: (
                "First, clearly understand the user's request. "
                "Identify the key elements and what they're asking for."
            ),
            ThinkingPhase.ANALYZING: (
                "Now analyze the components of this request. "
                "Break down the problem into smaller parts."
            ),
            ThinkingPhase.REASONING: (
                "Apply logical reasoning to determine the best approach. "
                "Consider alternatives and trade-offs."
            ),
            ThinkingPhase.SYNTHESIZING: (
                "Combine your analysis into a coherent response. "
                "Ensure all parts fit together logically."
            ),
            ThinkingPhase.VALIDATING: (
                "Validate your response. Check for errors, inconsistencies, "
                "or missing information. Be critical."
            ),
            ThinkingPhase.REFINING: (
                "Refine and improve the response based on validation. "
                "Make it clearer, more accurate, and more helpful."
            )
        }
        
        parts = [
            f"Query: {query}",
            f"\n{phase_instructions[phase]}"
        ]
        
        if previous_steps:
            parts.append("\nPrevious thinking:")
            for step in previous_steps:
                parts.append(f"- [{step.phase.value}]: {step.content[:200]}...")
        
        if context:
            parts.append(f"\nContext: {json.dumps(context)}")
        
        return "\n".join(parts)
    
    async def _call_llm(self, prompt: str, config: ThinkingModeConfig) -> str:
        """Call the LLM with timeout"""
        try:
            # Actual LLM call would go here
            # For now, simulate
            return await self._simulate_response(prompt, ThinkingPhase.REASONING, config)
        except asyncio.TimeoutError:
            logger.warning(f"LLM call timed out after {config.timeout_seconds}s")
            return "I need more time to think about this."
    
    async def _simulate_response(
        self,
        query: str,
        phase: ThinkingPhase,
        config: ThinkingModeConfig
    ) -> str:
        """Simulate LLM response for testing"""
        # Simulate processing time based on mode
        delays = {
            ThinkingMode.QUICK: 0.2,
            ThinkingMode.STANDARD: 0.5,
            ThinkingMode.DEEP: 1.0,
            ThinkingMode.RECURSIVE: 2.0
        }
        await asyncio.sleep(delays.get(config.mode, 0.5))
        
        responses = {
            ThinkingPhase.UNDERSTANDING: f"I understand you're asking about: {query[:100]}",
            ThinkingPhase.ANALYZING: f"Analyzing the key components of your request...",
            ThinkingPhase.REASONING: f"Based on my analysis, here's what I recommend...",
            ThinkingPhase.SYNTHESIZING: f"Putting it all together: {query[:50]}...",
            ThinkingPhase.VALIDATING: f"I've validated my response and it appears correct.",
            ThinkingPhase.REFINING: f"Here's my refined response to: {query[:50]}"
        }
        
        return responses.get(phase, "Thinking...")
    
    def _assess_confidence(self, response: str, phase: ThinkingPhase) -> float:
        """Assess confidence of a response"""
        # Simple heuristics for confidence
        confidence = 0.8
        
        # Lower confidence for short responses
        if len(response) < 50:
            confidence -= 0.2
        
        # Lower confidence if contains uncertainty markers
        uncertainty_markers = ["might", "possibly", "not sure", "maybe", "I think"]
        for marker in uncertainty_markers:
            if marker.lower() in response.lower():
                confidence -= 0.1
        
        # Higher confidence for validation phase
        if phase == ThinkingPhase.VALIDATING:
            confidence += 0.1
        
        return max(0.1, min(1.0, confidence))
    
    def _mode_priority(self, mode: ThinkingMode) -> int:
        """Get priority level of a thinking mode (0=QUICK, 3=RECURSIVE)"""
        priority_map = {
            ThinkingMode.QUICK: 0,
            ThinkingMode.STANDARD: 1,
            ThinkingMode.DEEP: 2,
            ThinkingMode.RECURSIVE: 3
        }
        return priority_map.get(mode, 0)
    
    def _get_next_mode(self, current: ThinkingMode) -> ThinkingMode:
        """Get the next thinking mode for escalation"""
        escalation_order = [
            ThinkingMode.QUICK,
            ThinkingMode.STANDARD,
            ThinkingMode.DEEP,
            ThinkingMode.RECURSIVE
        ]
        
        idx = escalation_order.index(current)
        if idx < len(escalation_order) - 1:
            return escalation_order[idx + 1]
        return current
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get thinking engine metrics"""
        return {
            "total_queries": self.total_queries,
            "mode_usage": {m.value: c for m, c in self.mode_usage.items()},
            "escalations": self.escalations,
            "escalation_rate": self.escalations / self.total_queries if self.total_queries > 0 else 0,
            "context_adjustments": self.context_adjustments,
            "context_adjustment_rate": self.context_adjustments / self.total_queries if self.total_queries > 0 else 0,
            "context_manager_enabled": self.context_manager is not None
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_thinking_engine: Optional[ExtendedThinkingEngine] = None

def get_thinking_engine() -> ExtendedThinkingEngine:
    """Get or create the global thinking engine"""
    global _thinking_engine
    if _thinking_engine is None:
        _thinking_engine = ExtendedThinkingEngine()
    return _thinking_engine


# ============================================================================
# API MODELS
# ============================================================================

class ThinkRequest(BaseModel):
    query: str
    mode: str = "standard"
    context: Optional[Dict[str, Any]] = None


class ThinkResponse(BaseModel):
    mode: str
    response: str
    thinking_steps: List[Dict[str, Any]]
    total_duration_ms: float
    energy_consumed: int
    confidence: float


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def create_thinking_prompt_wrapper(base_prompt: str, mode: ThinkingMode) -> str:
    """Wrap a prompt with thinking mode instructions"""
    mode_instructions = {
        ThinkingMode.QUICK: (
            "Respond quickly and concisely. "
            "Give a direct answer in 1-2 sentences."
        ),
        ThinkingMode.STANDARD: (
            "Think through this carefully. "
            "Provide a clear explanation with your reasoning."
        ),
        ThinkingMode.DEEP: (
            "Analyze this thoroughly from multiple angles. "
            "Consider edge cases, alternatives, and provide detailed reasoning. "
            "Structure your response with clear sections."
        ),
        ThinkingMode.RECURSIVE: (
            "This requires deep analysis. "
            "First, understand the problem completely. "
            "Then analyze all components and their relationships. "
            "Reason through possible solutions and their trade-offs. "
            "Synthesize your findings into a comprehensive response. "
            "Finally, validate your reasoning and refine if needed. "
            "Show your thinking process step by step."
        )
    }
    
    instruction = mode_instructions.get(mode, mode_instructions[ThinkingMode.STANDARD])
    
    return f"""<thinking_mode>{mode.value}</thinking_mode>
<instruction>{instruction}</instruction>

{base_prompt}"""


def extract_thinking_from_response(response: str) -> tuple[str, List[str]]:
    """Extract thinking tags and final response from LLM output"""
    import re
    
    # Find thinking blocks
    thinking_pattern = r'<think(?:ing)?>(.*?)</think(?:ing)?>'
    thinking_blocks = re.findall(thinking_pattern, response, re.DOTALL)
    
    # Remove thinking blocks from response
    clean_response = re.sub(thinking_pattern, '', response, flags=re.DOTALL).strip()
    
    return clean_response, thinking_blocks
