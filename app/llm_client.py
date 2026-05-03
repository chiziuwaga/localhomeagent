"""
Local LLM Client - Ollama and LM Studio Integration
Provides unified interface for local AI inference with automatic fallback

Features:
- Multi-provider support (Ollama, LM Studio)
- Automatic provider detection and fallback
- Context-aware token management (integrates with context_manager)
- Streaming response support
"""

import httpx
import asyncio
import json
import os
from typing import Optional, AsyncGenerator, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import logging

# Conditional import to avoid circular dependencies
if TYPE_CHECKING:
    from context_manager import ContextManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    NONE = "none"


@dataclass
class LLMConfig:
    """Configuration for LLM providers"""
    ollama_url: str = "http://localhost:11434"
    lm_studio_url: str = "http://localhost:1234"
    default_model: str = "llama3.2:3b"
    fallback_model: str = "llama3.2:1b"
    timeout: float = 120.0
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class LLMResponse:
    """Structured response from LLM"""
    content: str
    model: str
    provider: LLMProvider
    tokens_used: int = 0
    thinking: Optional[str] = None


class LocalLLMClient:
    """
    Unified client for local LLM inference
    Supports Ollama and LM Studio with automatic detection and fallback
    
    Now supports context-aware token management:
    - Tracks token usage per conversation
    - Integrates with ContextManager for budget management
    - Automatically adjusts max_tokens based on context availability
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._active_provider: Optional[LLMProvider] = None
        self._available_models: List[str] = []
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
        self._context_manager: Optional[Any] = None  # ContextManager instance
        self._total_tokens_used: int = 0  # Session tracking
        self._runtime_config: Optional[Dict[str, str]] = self._load_runtime_config()

    def _load_runtime_config(self) -> Optional[Dict[str, str]]:
        """Load runtime configuration if available"""
        try:
            config_path = "config/llm_runtime.json"
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load runtime config: {e}")
        return None
    
    def set_context_manager(self, context_manager: Any) -> None:
        """
        Set the context manager for token tracking.
        
        Args:
            context_manager: ContextManager instance from context_manager.py
        """
        self._context_manager = context_manager
        logger.info(f"Context manager attached to LLM client")
    
    def get_context_aware_max_tokens(self, requested_max: int) -> int:
        """
        Adjust max_tokens based on available context window.
        
        Args:
            requested_max: Originally requested max tokens
        
        Returns:
            Adjusted max tokens respecting context limits
        """
        if self._context_manager is None:
            return requested_max
        
        try:
            budget = self._context_manager.get_thinking_budget()
            available = budget.available
            
            # Use the smaller of requested or available
            adjusted = min(requested_max, available)
            
            if adjusted < requested_max:
                logger.info(
                    f"Context-aware adjustment: max_tokens {requested_max} -> {adjusted} "
                    f"(context limit)"
                )
            
            return max(50, adjusted)  # Minimum 50 tokens for useful response
        except Exception as e:
            logger.warning(f"Failed to get context budget: {e}")
            return requested_max
    
    def report_token_usage(self, role: str, content: str, tokens: int = 0) -> None:
        """
        Report token usage to the context manager.
        
        Args:
            role: Message role (user/assistant/system)
            content: Message content
            tokens: Actual token count if known
        """
        self._total_tokens_used += tokens
        
        if self._context_manager is not None:
            try:
                self._context_manager.add_message(role, content)
            except Exception as e:
                logger.warning(f"Failed to report to context manager: {e}")
    
    async def detect_provider(self) -> LLMProvider:
        """Detect which LLM provider is available"""
        
        # Try Ollama first (more common)
        try:
            response = await self._client.get(f"{self.config.ollama_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                self._available_models = [m["name"] for m in data.get("models", [])]
                self._active_provider = LLMProvider.OLLAMA
                logger.info(f"Detected Ollama with models: {self._available_models}")
                return LLMProvider.OLLAMA
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
        
        # Try LM Studio
        try:
            response = await self._client.get(f"{self.config.lm_studio_url}/v1/models")
            if response.status_code == 200:
                data = response.json()
                self._available_models = [m["id"] for m in data.get("data", [])]
                self._active_provider = LLMProvider.LM_STUDIO
                logger.info(f"Detected LM Studio with models: {self._available_models}")
                return LLMProvider.LM_STUDIO
        except Exception as e:
            logger.debug(f"LM Studio not available: {e}")
        
        self._active_provider = LLMProvider.NONE
        logger.warning("No local LLM provider detected")
        return LLMProvider.NONE
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models with metadata"""
        if not self._active_provider:
            await self.detect_provider()
        
        models = []
        for model_name in self._available_models:
            models.append({
                "id": model_name,
                "name": model_name.replace(":", " ").title(),
                "provider": self._active_provider.value if self._active_provider else "none",
                "recommended": model_name in ["llama3.2:1b", "llama3.2:3b", "llama-3.2-1b-instruct", "llama-3.2-3b-instruct"]
            })
        
        return models
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        respect_context_limits: bool = True
    ) -> LLMResponse:
        """
        Generate completion from local LLM
        
        Args:
            prompt: User prompt
            model: Model to use (defaults to config.default_model)
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            respect_context_limits: If True, adjust max_tokens based on context availability
            
        Returns:
            LLMResponse with content and metadata
        """
        if not self._active_provider:
            await self.detect_provider()
        
        if self._active_provider == LLMProvider.NONE:
            return LLMResponse(
                content="No local LLM available. Please install Ollama or LM Studio.",
                model="none",
                provider=LLMProvider.NONE
            )
        
        # Priority: explicit argument > runtime config > default config
        if model is None and self._runtime_config:
            model = self._runtime_config.get("model")
            
        model = model or self.config.default_model
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        
        # Context-aware adjustment
        if respect_context_limits:
            max_tokens = self.get_context_aware_max_tokens(max_tokens)
        
        # Report user message to context manager
        self.report_token_usage("user", prompt)
        
        try:
            if self._active_provider == LLMProvider.OLLAMA:
                response = await self._generate_ollama(
                    prompt, model, system_prompt, temperature, max_tokens
                )
            else:
                response = await self._generate_lm_studio(
                    prompt, model, system_prompt, temperature, max_tokens
                )
            
            # Report assistant response to context manager
            self.report_token_usage("assistant", response.content, response.tokens_used)
            
            return response
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            # Try fallback model
            if model != self.config.fallback_model:
                logger.info(f"Trying fallback model: {self.config.fallback_model}")
                return await self.generate(
                    prompt, self.config.fallback_model, system_prompt, temperature, max_tokens, respect_context_limits
                )
            raise
    
    async def _generate_ollama(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """Generate using Ollama API"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self._client.post(
            f"{self.config.ollama_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
        )
        response.raise_for_status()
        data = response.json()
        
        return LLMResponse(
            content=data["message"]["content"],
            model=model,
            provider=LLMProvider.OLLAMA,
            tokens_used=data.get("eval_count", 0)
        )
    
    async def _generate_lm_studio(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """Generate using LM Studio OpenAI-compatible API"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self._client.post(
            f"{self.config.lm_studio_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
        )
        response.raise_for_status()
        data = response.json()
        
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=model,
            provider=LLMProvider.LM_STUDIO,
            tokens_used=data.get("usage", {}).get("total_tokens", 0)
        )
    
    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream generation from local LLM
        
        Yields:
            Content chunks as they're generated
        """
        if not self._active_provider:
            await self.detect_provider()
        
        if self._active_provider == LLMProvider.NONE:
            yield "No local LLM available. Please install Ollama or LM Studio."
            return
        
        model = model or self.config.default_model
        temperature = temperature or self.config.temperature
        
        if self._active_provider == LLMProvider.OLLAMA:
            async for chunk in self._stream_ollama(prompt, model, system_prompt, temperature):
                yield chunk
        else:
            async for chunk in self._stream_lm_studio(prompt, model, system_prompt, temperature):
                yield chunk
    
    async def _stream_ollama(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        temperature: float
    ) -> AsyncGenerator[str, None]:
        """Stream from Ollama"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async with self._client.stream(
            "POST",
            f"{self.config.ollama_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": temperature}
            }
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    
    async def _stream_lm_studio(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        temperature: float
    ) -> AsyncGenerator[str, None]:
        """Stream from LM Studio"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async with self._client.stream(
            "POST",
            f"{self.config.lm_studio_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    
    def get_context_stats(self) -> Dict[str, Any]:
        """
        Get context and token usage statistics.
        
        Returns:
            Dictionary with token usage and context stats
        """
        stats = {
            "total_tokens_used_session": self._total_tokens_used,
            "context_manager_active": self._context_manager is not None,
            "active_provider": self._active_provider.value if self._active_provider else "none",
            "available_models_count": len(self._available_models)
        }
        
        if self._context_manager is not None:
            try:
                budget = self._context_manager.get_thinking_budget()
                stats["context_window_total"] = self._context_manager.context_window
                stats["context_tokens_used"] = self._context_manager.tokens_used
                stats["context_tokens_available"] = budget.available
                stats["context_utilization_percent"] = round(
                    (self._context_manager.tokens_used / self._context_manager.context_window) * 100, 1
                )
                stats["should_summarize"] = self._context_manager.should_summarize()
            except Exception as e:
                stats["context_error"] = str(e)
        
        return stats
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()


# Singleton instance for easy access
_llm_client: Optional[LocalLLMClient] = None


def get_llm_client() -> LocalLLMClient:
    """Get or create the singleton LLM client"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LocalLLMClient()
    return _llm_client


# Home Agent specific prompts
HOME_AGENT_SYSTEM_PROMPT = """You are a helpful home assistant for a co-living property. 

Your responsibilities:
- Welcome guests and help them with WiFi access
- Answer questions about house rules and amenities
- Help residents with general inquiries
- Coordinate with the admin for special requests
- Control smart home devices when authorized

Be friendly, concise, and helpful. Always prioritize safety and security.
If you're unsure about something, recommend contacting the admin.

House context will be provided with each message."""


GUEST_WELCOME_PROMPT = """Welcome! You've connected to the home network.

I'm your AI home assistant. I can help you with:
- 🏠 House information and rules
- 📶 WiFi and connectivity
- 🔑 Access and amenities
- 💬 Contacting residents

How can I assist you today?"""


async def test_connection():
    """Test LLM connection and print status"""
    client = get_llm_client()
    provider = await client.detect_provider()
    
    print(f"Provider: {provider.value}")
    
    if provider != LLMProvider.NONE:
        models = await client.get_available_models()
        print(f"Available models: {[m['id'] for m in models]}")
        
        # Quick test
        response = await client.generate(
            "Say 'Hello, I am working!' in exactly 5 words.",
            system_prompt="You are a helpful assistant."
        )
        print(f"Test response: {response.content}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
