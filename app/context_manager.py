"""
Context Manager for Model-Aware Agentic Architecture
Handles context window limits, token budgeting, and history management.

This module ensures downstream components adapt to the selected model's
context window size, preventing truncation errors and optimizing performance.

Architecture Impact:
- extended_thinking.py: Scales thinking depth based on available context
- llm_client.py: Tracks token usage and reserves space for responses
- tool_graph.py: Budgets tokens for tool calls and responses
- Chat history: Implements rolling window with summarization
"""

import json
import logging
import tiktoken
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# MODEL CONTEXT CONFIGURATIONS
# ============================================================================

class ModelFamily(str, Enum):
    """Model families with different context handling characteristics"""
    LLAMA = "llama"
    MISTRAL = "mistral"
    PHI = "phi"
    QWEN = "qwen"
    GEMMA = "gemma"
    UNKNOWN = "unknown"


@dataclass
class ModelContextConfig:
    """
    Configuration for a specific model's context handling.
    
    All downstream components should query this to understand limits.
    """
    model_id: str
    context_window: int          # Total context window (tokens)
    max_output_tokens: int       # Max tokens model can generate
    
    # Computed budgets (set automatically)
    system_prompt_budget: int = 0
    chat_history_budget: int = 0
    tool_response_budget: int = 0
    thinking_budget: int = 0
    response_budget: int = 0
    safety_margin: int = 0
    
    # Model characteristics
    family: ModelFamily = ModelFamily.UNKNOWN
    supports_function_calling: bool = False
    supports_vision: bool = False
    tokens_per_second: float = 0.0  # For time estimation
    
    def __post_init__(self):
        """Calculate token budgets based on context window"""
        # Reserve percentages of context window
        self.safety_margin = int(self.context_window * 0.05)  # 5% safety buffer
        usable_context = self.context_window - self.safety_margin
        
        # Budget allocation strategy:
        # - System prompt: 10%
        # - Chat history: 50%
        # - Tool responses: 15%
        # - Thinking: 10%
        # - Response: 15%
        self.system_prompt_budget = int(usable_context * 0.10)
        self.chat_history_budget = int(usable_context * 0.50)
        self.tool_response_budget = int(usable_context * 0.15)
        self.thinking_budget = int(usable_context * 0.10)
        self.response_budget = int(usable_context * 0.15)
    
    @property
    def available_for_input(self) -> int:
        """Tokens available for user input (history + current message)"""
        return (
            self.chat_history_budget + 
            self.system_prompt_budget - 
            self.safety_margin
        )
    
    def get_thinking_token_limit(self, mode: str) -> int:
        """
        Get max tokens for thinking based on mode and available budget.
        
        Downstream Impact: extended_thinking.py uses this to set max_tokens
        """
        mode_ratios = {
            "quick": 0.1,      # 10% of thinking budget
            "standard": 0.3,   # 30%
            "deep": 0.7,       # 70%
            "recursive": 1.0   # 100% (may need multiple passes)
        }
        ratio = mode_ratios.get(mode.lower(), 0.3)
        return int(self.thinking_budget * ratio)


# ============================================================================
# MODEL REGISTRY
# ============================================================================

# Pre-configured models with accurate context windows
MODEL_REGISTRY: Dict[str, ModelContextConfig] = {
    # Llama 3.2 family
    "llama3.2:1b": ModelContextConfig(
        model_id="llama3.2:1b",
        context_window=128_000,
        max_output_tokens=4_096,
        family=ModelFamily.LLAMA,
        supports_function_calling=True,
        tokens_per_second=80.0
    ),
    "llama3.2:3b": ModelContextConfig(
        model_id="llama3.2:3b",
        context_window=128_000,
        max_output_tokens=4_096,
        family=ModelFamily.LLAMA,
        supports_function_calling=True,
        tokens_per_second=45.0
    ),
    
    # Llama 3.1 family
    "llama3.1:8b": ModelContextConfig(
        model_id="llama3.1:8b",
        context_window=128_000,
        max_output_tokens=4_096,
        family=ModelFamily.LLAMA,
        supports_function_calling=True,
        tokens_per_second=25.0
    ),
    
    # Mistral family
    "mistral:7b-instruct": ModelContextConfig(
        model_id="mistral:7b-instruct",
        context_window=32_000,
        max_output_tokens=4_096,
        family=ModelFamily.MISTRAL,
        supports_function_calling=True,
        tokens_per_second=30.0
    ),
    
    # Phi family (Microsoft)
    "phi3:mini": ModelContextConfig(
        model_id="phi3:mini",
        context_window=128_000,
        max_output_tokens=4_096,
        family=ModelFamily.PHI,
        supports_function_calling=False,
        tokens_per_second=50.0
    ),
    
    # Qwen family (Alibaba)
    "qwen2.5-coder:7b": ModelContextConfig(
        model_id="qwen2.5-coder:7b",
        context_window=128_000,
        max_output_tokens=8_192,
        family=ModelFamily.QWEN,
        supports_function_calling=True,
        tokens_per_second=28.0
    ),
    
    # Gemma family (Google)
    "gemma2:9b": ModelContextConfig(
        model_id="gemma2:9b",
        context_window=8_192,
        max_output_tokens=2_048,
        family=ModelFamily.GEMMA,
        supports_function_calling=False,
        tokens_per_second=22.0
    ),
}


def get_model_config(model_id: str) -> ModelContextConfig:
    """
    Get context configuration for a model.
    
    Falls back to conservative defaults for unknown models.
    """
    # Exact match
    if model_id in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_id]
    
    # Try without version tag (e.g., "llama3.2:3b-instruct" -> "llama3.2:3b")
    base_model = model_id.split("-")[0] if "-" in model_id else model_id
    if base_model in MODEL_REGISTRY:
        config = MODEL_REGISTRY[base_model]
        # Return copy with updated model_id
        return ModelContextConfig(
            model_id=model_id,
            context_window=config.context_window,
            max_output_tokens=config.max_output_tokens,
            family=config.family,
            supports_function_calling=config.supports_function_calling,
            tokens_per_second=config.tokens_per_second
        )
    
    # Unknown model - use conservative 8K context
    logger.warning(f"Unknown model '{model_id}', using conservative 8K context")
    return ModelContextConfig(
        model_id=model_id,
        context_window=8_192,
        max_output_tokens=2_048,
        family=ModelFamily.UNKNOWN
    )


# ============================================================================
# TOKEN COUNTER
# ============================================================================

class TokenCounter:
    """
    Counts tokens for text using tiktoken (GPT tokenizer as approximation).
    
    Different models use different tokenizers, but tiktoken provides
    a reasonable approximation for most modern LLMs.
    """
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize with a tiktoken encoding.
        
        cl100k_base is used by GPT-4 and is a good general approximation.
        """
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            # Fallback to character-based estimation
            logger.warning("tiktoken not available, using character estimation")
            self.encoding = None
    
    def count(self, text: str) -> int:
        """Count tokens in text"""
        if not text:
            return 0
        
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Rough estimation: ~4 characters per token
            return len(text) // 4
    
    def count_messages(self, messages: List[Dict[str, Any]]) -> int:
        """Count tokens in a list of chat messages"""
        total = 0
        for msg in messages:
            # Each message has role + content + overhead
            total += 4  # Message overhead
            total += self.count(msg.get("role", ""))
            total += self.count(msg.get("content", ""))
            
            # Tool calls add extra tokens
            if "tool_calls" in msg:
                total += self.count(json.dumps(msg["tool_calls"]))
        
        return total


# ============================================================================
# CONTEXT TRACKER
# ============================================================================

@dataclass
class ContextUsage:
    """Tracks current context usage"""
    system_prompt_tokens: int = 0
    chat_history_tokens: int = 0
    current_message_tokens: int = 0
    tool_response_tokens: int = 0
    thinking_tokens: int = 0
    
    @property
    def total_used(self) -> int:
        return (
            self.system_prompt_tokens +
            self.chat_history_tokens +
            self.current_message_tokens +
            self.tool_response_tokens +
            self.thinking_tokens
        )


class ContextTracker:
    """
    Tracks context usage and provides budget recommendations.
    
    Downstream components should use this to:
    - Check remaining budget before operations
    - Get recommended token limits
    - Trigger history summarization when needed
    """
    
    def __init__(self, model_config: ModelContextConfig):
        self.config = model_config
        self.counter = TokenCounter()
        self.usage = ContextUsage()
        self._message_history: List[Dict[str, Any]] = []
    
    def set_system_prompt(self, prompt: str) -> int:
        """Set system prompt and track its tokens"""
        tokens = self.counter.count(prompt)
        self.usage.system_prompt_tokens = tokens
        
        if tokens > self.config.system_prompt_budget:
            logger.warning(
                f"System prompt ({tokens} tokens) exceeds budget "
                f"({self.config.system_prompt_budget} tokens)"
            )
        
        return tokens
    
    def add_message(self, message: Dict[str, Any]) -> int:
        """Add a message to history and track tokens"""
        tokens = self.counter.count_messages([message])
        self._message_history.append(message)
        self.usage.chat_history_tokens = self.counter.count_messages(self._message_history)
        return tokens
    
    def get_remaining_context(self) -> int:
        """Get remaining tokens available"""
        return self.config.context_window - self.usage.total_used - self.config.safety_margin
    
    def get_remaining_for_response(self) -> int:
        """Get tokens available for model response"""
        remaining = self.get_remaining_context()
        return min(remaining, self.config.max_output_tokens)
    
    def needs_summarization(self) -> bool:
        """Check if chat history should be summarized"""
        return self.usage.chat_history_tokens > self.config.chat_history_budget * 0.9
    
    def get_recommended_thinking_tokens(self, mode: str) -> int:
        """Get recommended max tokens for thinking mode"""
        base_limit = self.config.get_thinking_token_limit(mode)
        remaining = self.get_remaining_context()
        
        # Don't exceed remaining context
        return min(base_limit, remaining // 2)  # Reserve half for response
    
    def get_context_report(self) -> Dict[str, Any]:
        """Get detailed context usage report"""
        return {
            "model": self.config.model_id,
            "context_window": self.config.context_window,
            "usage": {
                "system_prompt": self.usage.system_prompt_tokens,
                "chat_history": self.usage.chat_history_tokens,
                "current_message": self.usage.current_message_tokens,
                "tool_responses": self.usage.tool_response_tokens,
                "thinking": self.usage.thinking_tokens,
                "total": self.usage.total_used
            },
            "remaining": self.get_remaining_context(),
            "remaining_for_response": self.get_remaining_for_response(),
            "needs_summarization": self.needs_summarization(),
            "budgets": {
                "system_prompt": self.config.system_prompt_budget,
                "chat_history": self.config.chat_history_budget,
                "tool_responses": self.config.tool_response_budget,
                "thinking": self.config.thinking_budget,
                "response": self.config.response_budget
            }
        }


# ============================================================================
# HISTORY SUMMARIZER
# ============================================================================

class HistorySummarizer:
    """
    Summarizes chat history when context limit approaches.
    
    Strategies:
    1. Keep most recent N messages intact
    2. Summarize older messages into a single context block
    3. Extract key facts/decisions from old messages
    """
    
    def __init__(self, counter: TokenCounter):
        self.counter = counter
    
    def summarize_history(
        self,
        messages: List[Dict[str, Any]],
        target_tokens: int,
        summarizer_fn: Optional[Callable[[str], str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Summarize message history to fit within target token budget.
        
        Args:
            messages: Full message history
            target_tokens: Target token budget
            summarizer_fn: Optional LLM function to generate summary
        
        Returns:
            Condensed message list
        """
        if not messages:
            return []
        
        current_tokens = self.counter.count_messages(messages)
        
        # If already within budget, no summarization needed
        if current_tokens <= target_tokens:
            return messages
        
        # Strategy: Keep recent messages, summarize old ones
        # Keep at least last 5 messages intact
        keep_recent = min(5, len(messages))
        recent_messages = messages[-keep_recent:]
        old_messages = messages[:-keep_recent]
        
        if not old_messages:
            # Can't summarize further, return as is
            return messages
        
        # Generate summary of old messages
        if summarizer_fn:
            # Use LLM to summarize
            old_content = "\n".join([
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in old_messages
            ])
            summary = summarizer_fn(
                f"Summarize this conversation history concisely:\n{old_content}"
            )
        else:
            # Simple extractive summary
            summary = self._extractive_summary(old_messages)
        
        # Create summarized history
        summarized = [
            {
                "role": "system",
                "content": f"[Previous conversation summary: {summary}]"
            }
        ] + recent_messages
        
        return summarized
    
    def _extractive_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Create simple extractive summary without LLM"""
        # Extract key information
        facts = []
        
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")
            
            # Extract numbers (prices, dates, etc.)
            import re
            numbers = re.findall(r'\$[\d,]+|\d+(?:\.\d+)?%|\d{4}-\d{2}-\d{2}', content)
            if numbers:
                facts.append(f"Mentioned: {', '.join(numbers)}")
            
            # Extract decisions/confirmations
            if any(word in content.lower() for word in ["confirmed", "agreed", "decided", "set to"]):
                # Take first sentence
                first_sentence = content.split('.')[0]
                if len(first_sentence) < 100:
                    facts.append(first_sentence)
        
        if facts:
            return "; ".join(facts[:5])  # Keep top 5 facts
        else:
            return f"Discussed {len(messages)} messages about the property."


# ============================================================================
# ADAPTIVE THINKING RULES
# ============================================================================

class AdaptiveThinkingRules:
    """
    Adjusts thinking mode behavior based on model context limits.
    
    This is the key downstream integration point for extended_thinking.py
    """
    
    def __init__(self, model_config: ModelContextConfig):
        self.config = model_config
    
    def get_adjusted_config(self, mode: str, context_tracker: ContextTracker) -> Dict[str, Any]:
        """
        Get adjusted thinking configuration based on current context usage.
        
        Returns config dict that extended_thinking.py should use.
        """
        remaining = context_tracker.get_remaining_context()
        base_limit = self.config.get_thinking_token_limit(mode)
        
        # Adjust based on remaining context
        adjusted_limit = min(base_limit, remaining // 3)  # Reserve 2/3 for response
        
        # Scale temperature with context pressure
        # More context pressure = more focused/deterministic responses
        context_pressure = 1 - (remaining / self.config.context_window)
        base_temperature = {"quick": 0.3, "standard": 0.5, "deep": 0.7, "recursive": 0.7}
        adjusted_temperature = max(0.2, base_temperature.get(mode, 0.5) * (1 - context_pressure * 0.3))
        
        # Reduce iterations if context is tight
        base_iterations = {"quick": 1, "standard": 1, "deep": 2, "recursive": 3}
        adjusted_iterations = base_iterations.get(mode, 1)
        if context_pressure > 0.7:
            adjusted_iterations = 1  # Force single iteration when context is tight
        
        # Recommend mode downgrade if necessary
        recommended_mode = mode
        if mode == "recursive" and remaining < 10_000:
            recommended_mode = "deep"
            logger.info("Downgrading from RECURSIVE to DEEP due to context limits")
        elif mode == "deep" and remaining < 5_000:
            recommended_mode = "standard"
            logger.info("Downgrading from DEEP to STANDARD due to context limits")
        elif mode in ("standard", "deep", "recursive") and remaining < 2_000:
            recommended_mode = "quick"
            logger.info("Downgrading to QUICK due to context limits")
        
        return {
            "mode": recommended_mode,
            "max_tokens": adjusted_limit,
            "temperature": adjusted_temperature,
            "max_iterations": adjusted_iterations,
            "context_remaining": remaining,
            "context_pressure": context_pressure,
            "was_downgraded": recommended_mode != mode
        }
    
    def should_escalate_mode(
        self,
        current_mode: str,
        query_complexity: float,  # 0.0 to 1.0
        context_tracker: ContextTracker
    ) -> Optional[str]:
        """
        Determine if thinking mode should be escalated for complex queries.
        
        Returns new mode if escalation recommended, None otherwise.
        """
        remaining = context_tracker.get_remaining_context()
        
        # Don't escalate if context is tight
        if remaining < 10_000:
            return None
        
        mode_order = ["quick", "standard", "deep", "recursive"]
        current_idx = mode_order.index(current_mode) if current_mode in mode_order else 1
        
        # Escalate if query is complex and we have room
        if query_complexity > 0.7 and current_idx < 2:  # Below DEEP
            return "deep"
        elif query_complexity > 0.9 and current_idx < 3 and remaining > 30_000:
            return "recursive"
        
        return None


# ============================================================================
# MAIN CONTEXT MANAGER
# ============================================================================

class ContextManager:
    """
    Main context manager that coordinates all context-aware components.
    
    Usage:
        manager = ContextManager("llama3.2:3b")
        manager.set_system_prompt("You are a helpful assistant...")
        
        # Before generating response
        config = manager.get_thinking_config("standard")
        
        # Check if summarization needed
        if manager.needs_summarization():
            manager.summarize_history()
    """
    
    _instance: Optional["ContextManager"] = None
    _current_model: Optional[str] = None
    
    def __init__(self, model_id: str):
        self.model_config = get_model_config(model_id)
        self.tracker = ContextTracker(self.model_config)
        self.counter = TokenCounter()
        self.summarizer = HistorySummarizer(self.counter)
        self.thinking_rules = AdaptiveThinkingRules(self.model_config)
        
        logger.info(
            f"ContextManager initialized for {model_id}: "
            f"{self.model_config.context_window:,} tokens context"
        )
    
    @classmethod
    def get_instance(cls, model_id: Optional[str] = None) -> "ContextManager":
        """Get or create singleton instance"""
        if model_id and (cls._instance is None or cls._current_model != model_id):
            cls._instance = cls(model_id)
            cls._current_model = model_id
        
        if cls._instance is None:
            cls._instance = cls("llama3.2:3b")  # Default model
            cls._current_model = "llama3.2:3b"
        
        return cls._instance
    
    def set_system_prompt(self, prompt: str) -> int:
        """Set and track system prompt"""
        return self.tracker.set_system_prompt(prompt)
    
    def add_message(self, role: str, content: str) -> int:
        """Add message to history"""
        return self.tracker.add_message({"role": role, "content": content})
    
    def get_thinking_config(self, mode: str) -> Dict[str, Any]:
        """Get adjusted thinking configuration for current context state"""
        return self.thinking_rules.get_adjusted_config(mode, self.tracker)
    
    def needs_summarization(self) -> bool:
        """Check if history summarization is recommended"""
        return self.tracker.needs_summarization()
    
    def summarize_history(self, summarizer_fn: Optional[Callable[[str], str]] = None):
        """Summarize chat history to free up context"""
        self.tracker._message_history = self.summarizer.summarize_history(
            self.tracker._message_history,
            self.model_config.chat_history_budget,
            summarizer_fn
        )
        self.tracker.usage.chat_history_tokens = self.counter.count_messages(
            self.tracker._message_history
        )
    
    def get_max_response_tokens(self) -> int:
        """Get maximum tokens available for response"""
        return self.tracker.get_remaining_for_response()
    
    def get_context_report(self) -> Dict[str, Any]:
        """Get detailed context usage report"""
        return self.tracker.get_context_report()
    
    def should_auto_escalate(self, query: str) -> Optional[str]:
        """Check if thinking mode should auto-escalate based on query"""
        # Simple complexity estimation
        complexity = 0.0
        
        # Complex queries tend to be longer
        if len(query) > 500:
            complexity += 0.3
        
        # Questions with multiple parts
        if query.count("?") > 1:
            complexity += 0.2
        
        # Technical/analytical keywords
        complex_keywords = [
            "analyze", "compare", "evaluate", "calculate", "explain why",
            "pros and cons", "step by step", "in detail", "comprehensive"
        ]
        for keyword in complex_keywords:
            if keyword in query.lower():
                complexity += 0.15
        
        complexity = min(1.0, complexity)
        
        return self.thinking_rules.should_escalate_mode(
            "standard",  # Assume starting from standard
            complexity,
            self.tracker
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def estimate_tokens(text: str) -> int:
    """Quick token estimation without instantiating full counter"""
    return len(text) // 4


def get_model_context_window(model_id: str) -> int:
    """Get context window size for a model"""
    return get_model_config(model_id).context_window


def format_context_usage(report: Dict[str, Any]) -> str:
    """Format context report for display"""
    usage = report["usage"]
    budgets = report["budgets"]
    
    lines = [
        f"Model: {report['model']}",
        f"Context Window: {report['context_window']:,} tokens",
        "",
        "Usage:",
        f"  System Prompt: {usage['system_prompt']:,} / {budgets['system_prompt']:,}",
        f"  Chat History:  {usage['chat_history']:,} / {budgets['chat_history']:,}",
        f"  Tool Responses: {usage['tool_responses']:,} / {budgets['tool_responses']:,}",
        f"  Thinking:      {usage['thinking']:,} / {budgets['thinking']:,}",
        f"  Total Used:    {usage['total']:,}",
        "",
        f"Remaining: {report['remaining']:,} tokens",
        f"Needs Summarization: {'Yes' if report['needs_summarization'] else 'No'}"
    ]
    
    return "\n".join(lines)


# ============================================================================
# INTEGRATION HOOKS
# ============================================================================

# These functions are called by other modules to integrate context awareness

def get_thinking_limits_for_mode(model_id: str, mode: str) -> Dict[str, int]:
    """
    Get token limits for thinking mode.
    
    Called by: extended_thinking.py
    """
    manager = ContextManager.get_instance(model_id)
    config = manager.get_thinking_config(mode)
    return {
        "max_tokens": config["max_tokens"],
        "temperature": config["temperature"],
        "max_iterations": config["max_iterations"]
    }


def check_context_before_call(
    model_id: str,
    messages: List[Dict[str, Any]],
    estimated_response_tokens: int = 500
) -> Dict[str, Any]:
    """
    Check if there's enough context for an LLM call.
    
    Called by: llm_client.py before making API calls
    
    Returns:
        {
            "can_proceed": bool,
            "remaining_tokens": int,
            "recommendation": str,  # "proceed", "summarize", "reduce_response"
            "max_response_tokens": int
        }
    """
    config = get_model_config(model_id)
    counter = TokenCounter()
    
    message_tokens = counter.count_messages(messages)
    remaining = config.context_window - message_tokens - config.safety_margin
    
    if remaining < estimated_response_tokens:
        return {
            "can_proceed": False,
            "remaining_tokens": remaining,
            "recommendation": "summarize",
            "max_response_tokens": max(100, remaining)
        }
    elif remaining < estimated_response_tokens * 2:
        return {
            "can_proceed": True,
            "remaining_tokens": remaining,
            "recommendation": "reduce_response",
            "max_response_tokens": remaining - 100
        }
    else:
        return {
            "can_proceed": True,
            "remaining_tokens": remaining,
            "recommendation": "proceed",
            "max_response_tokens": min(remaining, config.max_output_tokens)
        }
