"""
Prompt Chains for Passphrase Verification (P3/N1.1)

Inspired by:
- Indie Dev Dan's embedded prompt chains
- Claude's coherence-driven consciousness patterns
- Dave Shap's recursive self-representation

This implements a multi-stage verification pipeline where each stage
reasons about the previous stage's output, creating an embedded
chain of verification that is extremely difficult to bypass.

Architecture:
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│   Stage 1      │────▶│   Stage 2      │────▶│   Stage 3      │
│  Lexical Parse │     │ Semantic Check │     │ Intent Verify  │
└────────────────┘     └────────────────┘     └────────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
    [reasoning]           [reasoning]           [reasoning]
        │                      │                      │
        └──────────────────────┴──────────────────────┘
                              │
                              ▼
                    ┌────────────────┐
                    │  Final Oracle  │
                    │ (Meta-Reason)  │
                    └────────────────┘
"""

import logging
import hashlib
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ChainStage(Enum):
    """Stages of the verification prompt chain"""
    LEXICAL = "lexical"       # Parse tokens, structure
    SEMANTIC = "semantic"     # Check meaning, context
    INTENT = "intent"         # Verify user intent
    ORACLE = "oracle"         # Final meta-reasoning


class VerificationOutcome(Enum):
    """Possible outcomes from verification"""
    PASS = "pass"
    FAIL = "fail"
    CHALLENGE = "challenge"   # Needs additional verification
    ESCALATE = "escalate"     # Needs human review


@dataclass
class ChainContext:
    """Context passed through the prompt chain"""
    user_id: str
    session_id: str
    input_text: str
    expected_passphrase_hash: str
    timestamp: datetime = field(default_factory=datetime.now)
    stages_completed: List[str] = field(default_factory=list)
    stage_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    reasoning_chain: List[str] = field(default_factory=list)
    energy_consumed: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """Result from a single chain stage"""
    stage: ChainStage
    passed: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    energy_cost: float = 1.0
    next_action: Optional[str] = None


class ChainStageProcessor(ABC):
    """Abstract base for chain stage processors"""
    
    @abstractmethod
    async def process(self, context: ChainContext) -> StageResult:
        """Process this stage of the chain"""
        pass
    
    @abstractmethod
    def get_prompt(self, context: ChainContext) -> str:
        """Get the prompt for this stage"""
        pass


class LexicalStage(ChainStageProcessor):
    """
    Stage 1: Lexical Analysis
    
    Parses the input for structural validity before any semantic analysis.
    This catches injection attempts and malformed inputs early.
    
    Checks:
    - Token count and structure
    - Special character patterns
    - Entropy analysis (randomness detection)
    - Known attack pattern matching
    """
    
    # Patterns that indicate potential injection attacks
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|all)",
        r"forget\s+(everything|instructions)",
        r"system\s*:",
        r"<\/?[a-z]+>",  # HTML/XML tags
        r"\{\{.*\}\}",   # Template injection
        r"\\n\\n",       # Escaped newlines
        r"```",          # Markdown code blocks
    ]
    
    def __init__(self):
        self.attack_pattern_re = re.compile(
            "|".join(self.INJECTION_PATTERNS),
            re.IGNORECASE
        )
    
    async def process(self, context: ChainContext) -> StageResult:
        """Analyze lexical structure of input"""
        input_text = context.input_text
        
        # Check 1: Length bounds
        if len(input_text) < 4 or len(input_text) > 200:
            return StageResult(
                stage=ChainStage.LEXICAL,
                passed=False,
                confidence=0.95,
                reasoning="Input length outside acceptable bounds (4-200 chars)",
                evidence={"length": len(input_text)},
                energy_cost=0.5,
            )
        
        # Check 2: Injection pattern detection
        injection_match = self.attack_pattern_re.search(input_text)
        if injection_match:
            return StageResult(
                stage=ChainStage.LEXICAL,
                passed=False,
                confidence=0.98,
                reasoning=f"Detected potential injection pattern: '{injection_match.group()}'",
                evidence={"matched_pattern": injection_match.group()},
                energy_cost=0.5,
                next_action="block_and_log",
            )
        
        # Check 3: Entropy analysis (detect random gibberish vs structured phrase)
        entropy = self._calculate_entropy(input_text)
        if entropy > 4.5:  # High entropy = potentially random/adversarial
            return StageResult(
                stage=ChainStage.LEXICAL,
                passed=False,
                confidence=0.75,
                reasoning=f"Input has unusually high entropy ({entropy:.2f}), may be adversarial",
                evidence={"entropy": entropy},
                energy_cost=0.5,
                next_action="challenge",
            )
        
        # Check 4: Token structure
        tokens = input_text.split()
        special_char_ratio = sum(1 for c in input_text if not c.isalnum() and c != ' ') / len(input_text)
        
        # All checks passed
        return StageResult(
            stage=ChainStage.LEXICAL,
            passed=True,
            confidence=0.85,
            reasoning=f"Lexical analysis passed: {len(tokens)} tokens, entropy={entropy:.2f}, special_char_ratio={special_char_ratio:.2f}",
            evidence={
                "token_count": len(tokens),
                "entropy": entropy,
                "special_char_ratio": special_char_ratio,
            },
            energy_cost=0.5,
        )
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text"""
        import math
        from collections import Counter
        
        if not text:
            return 0.0
        
        freq = Counter(text.lower())
        length = len(text)
        
        entropy = 0.0
        for count in freq.values():
            prob = count / length
            entropy -= prob * math.log2(prob)
        
        return entropy
    
    def get_prompt(self, context: ChainContext) -> str:
        """Lexical stage doesn't use LLM prompts (rule-based)"""
        return ""


class SemanticStage(ChainStageProcessor):
    """
    Stage 2: Semantic Analysis
    
    Analyzes the meaning and context of the passphrase.
    Uses the energy model to determine if the semantic content
    matches expected patterns for legitimate passphrases.
    
    This stage can use local LLM for semantic understanding.
    """
    
    # Semantic red flags
    RED_FLAG_PHRASES = [
        "bypass", "override", "admin", "sudo",
        "emergency", "debug", "test", "skip",
        "master", "backdoor", "root"
    ]
    
    def __init__(self):
        self.red_flag_re = re.compile(
            r"\b(" + "|".join(self.RED_FLAG_PHRASES) + r")\b",
            re.IGNORECASE
        )
    
    async def process(self, context: ChainContext) -> StageResult:
        """Analyze semantic content of input"""
        input_text = context.input_text
        
        # Get lexical stage results for context
        lexical_result = context.stage_results.get(ChainStage.LEXICAL.value, {})
        
        # Check 1: Red flag phrase detection
        red_flags = self.red_flag_re.findall(input_text)
        if red_flags:
            return StageResult(
                stage=ChainStage.SEMANTIC,
                passed=False,
                confidence=0.88,
                reasoning=f"Detected semantic red flags: {', '.join(red_flags)}",
                evidence={"red_flags": red_flags},
                energy_cost=1.0,
                next_action="challenge",
            )
        
        # Check 2: Passphrase structure (should be memorable, not random)
        word_count = len(input_text.split())
        avg_word_length = len(input_text.replace(" ", "")) / max(word_count, 1)
        
        # Good passphrases: 3-6 words, avg word length 4-8
        structure_score = 0.0
        if 3 <= word_count <= 6:
            structure_score += 0.5
        if 4 <= avg_word_length <= 8:
            structure_score += 0.5
        
        if structure_score < 0.5:
            return StageResult(
                stage=ChainStage.SEMANTIC,
                passed=False,
                confidence=0.65,
                reasoning=f"Passphrase structure unusual: {word_count} words, avg length {avg_word_length:.1f}",
                evidence={
                    "word_count": word_count,
                    "avg_word_length": avg_word_length,
                    "structure_score": structure_score,
                },
                energy_cost=1.0,
                next_action="challenge",
            )
        
        # Check 3: Hash comparison (actual passphrase verification)
        input_hash = hashlib.sha256(input_text.strip().lower().encode()).hexdigest()
        hash_match = input_hash == context.expected_passphrase_hash
        
        if not hash_match:
            return StageResult(
                stage=ChainStage.SEMANTIC,
                passed=False,
                confidence=0.99,
                reasoning="Passphrase hash mismatch",
                evidence={"hash_match": False},
                energy_cost=1.0,
            )
        
        # All checks passed
        return StageResult(
            stage=ChainStage.SEMANTIC,
            passed=True,
            confidence=0.92,
            reasoning=f"Semantic analysis passed: structure_score={structure_score}, hash_match=True",
            evidence={
                "word_count": word_count,
                "avg_word_length": avg_word_length,
                "structure_score": structure_score,
                "hash_match": True,
            },
            energy_cost=1.0,
        )
    
    def get_prompt(self, context: ChainContext) -> str:
        """Prompt for LLM-assisted semantic analysis"""
        return f"""Analyze the semantic content of this passphrase attempt:

Input: "{context.input_text}"

Previous stage (lexical) analysis:
{context.stage_results.get(ChainStage.LEXICAL.value, 'No prior analysis')}

Evaluate:
1. Does this appear to be a legitimate passphrase?
2. Are there any semantic red flags (bypass attempts, admin claims)?
3. What is your confidence level (0.0-1.0)?

Respond with structured reasoning."""


class IntentStage(ChainStageProcessor):
    """
    Stage 3: Intent Verification
    
    Determines if the user's intent is legitimate by analyzing:
    - Behavioral context (time of day, request frequency)
    - Session coherence (does this follow logically?)
    - Energy level of the action being authorized
    
    This is where we apply thermodynamic reasoning.
    """
    
    async def process(self, context: ChainContext) -> StageResult:
        """Verify user intent through behavioral analysis"""
        
        # Get previous stage results
        lexical = context.stage_results.get(ChainStage.LEXICAL.value, {})
        semantic = context.stage_results.get(ChainStage.SEMANTIC.value, {})
        
        # Check 1: Stage coherence (previous stages must have passed)
        if not lexical.get("passed", False) or not semantic.get("passed", False):
            return StageResult(
                stage=ChainStage.INTENT,
                passed=False,
                confidence=0.95,
                reasoning="Previous stages did not pass, intent cannot be verified",
                evidence={
                    "lexical_passed": lexical.get("passed", False),
                    "semantic_passed": semantic.get("passed", False),
                },
                energy_cost=1.5,
            )
        
        # Check 2: Time-of-day analysis (late night = higher suspicion)
        hour = context.timestamp.hour
        time_risk = 1.0
        if 0 <= hour < 6:
            time_risk = 1.5  # Late night
        elif 22 <= hour <= 23:
            time_risk = 1.2  # Evening
        
        # Check 3: Session coherence
        session_coherent = len(context.stages_completed) >= 2
        
        # Check 4: Aggregate confidence from previous stages
        lexical_conf = lexical.get("confidence", 0.5)
        semantic_conf = semantic.get("confidence", 0.5)
        aggregate_confidence = (lexical_conf + semantic_conf) / 2
        
        # Apply time risk to confidence
        adjusted_confidence = aggregate_confidence / time_risk
        
        # Threshold for passing
        if adjusted_confidence < 0.75:
            return StageResult(
                stage=ChainStage.INTENT,
                passed=False,
                confidence=adjusted_confidence,
                reasoning=f"Intent verification failed: adjusted_confidence={adjusted_confidence:.2f} < 0.75 threshold",
                evidence={
                    "time_risk": time_risk,
                    "hour": hour,
                    "aggregate_confidence": aggregate_confidence,
                    "session_coherent": session_coherent,
                },
                energy_cost=1.5,
                next_action="challenge",
            )
        
        return StageResult(
            stage=ChainStage.INTENT,
            passed=True,
            confidence=adjusted_confidence,
            reasoning=f"Intent verified: confidence={adjusted_confidence:.2f}, time_risk={time_risk}, session_coherent={session_coherent}",
            evidence={
                "time_risk": time_risk,
                "hour": hour,
                "aggregate_confidence": aggregate_confidence,
                "session_coherent": session_coherent,
            },
            energy_cost=1.5,
        )
    
    def get_prompt(self, context: ChainContext) -> str:
        """Prompt for LLM-assisted intent verification"""
        return f"""Verify the user's intent for this passphrase attempt:

User ID: {context.user_id}
Timestamp: {context.timestamp.isoformat()}
Input: "{context.input_text}"

Previous stage results:
- Lexical: {context.stage_results.get(ChainStage.LEXICAL.value, 'N/A')}
- Semantic: {context.stage_results.get(ChainStage.SEMANTIC.value, 'N/A')}

Reasoning chain so far:
{chr(10).join(context.reasoning_chain)}

Determine:
1. Is this a legitimate passphrase attempt?
2. What is the user's likely intent?
3. Should we proceed, challenge, or escalate?

Respond with your reasoning."""


class OracleStage(ChainStageProcessor):
    """
    Stage 4: Oracle (Meta-Reasoning)
    
    The final stage that performs meta-reasoning over all previous stages.
    This is the "recursive self-representation" stage that thinks about
    the thinking process itself.
    
    Inspired by Dave Shap's coherence-based consciousness model.
    """
    
    async def process(self, context: ChainContext) -> StageResult:
        """Meta-reasoning over the entire chain"""
        
        # Gather all previous results
        all_passed = all(
            context.stage_results.get(stage.value, {}).get("passed", False)
            for stage in [ChainStage.LEXICAL, ChainStage.SEMANTIC, ChainStage.INTENT]
        )
        
        # Calculate aggregate metrics
        total_confidence = sum(
            context.stage_results.get(stage.value, {}).get("confidence", 0)
            for stage in [ChainStage.LEXICAL, ChainStage.SEMANTIC, ChainStage.INTENT]
        ) / 3
        
        total_energy = context.energy_consumed
        
        # Meta-reasoning: Check for coherence across stages
        coherence_issues = []
        
        # Check 1: Confidence consistency
        confidences = [
            context.stage_results.get(stage.value, {}).get("confidence", 0)
            for stage in [ChainStage.LEXICAL, ChainStage.SEMANTIC, ChainStage.INTENT]
        ]
        conf_variance = max(confidences) - min(confidences) if confidences else 0
        if conf_variance > 0.3:
            coherence_issues.append(f"High confidence variance ({conf_variance:.2f})")
        
        # Check 2: Reasoning chain completeness
        if len(context.reasoning_chain) < 3:
            coherence_issues.append("Incomplete reasoning chain")
        
        # Check 3: Energy budget
        if total_energy > 10.0:
            coherence_issues.append(f"High energy consumption ({total_energy:.1f})")
        
        # Final decision
        if not all_passed:
            return StageResult(
                stage=ChainStage.ORACLE,
                passed=False,
                confidence=total_confidence,
                reasoning=f"Oracle DENIES: Not all stages passed. Issues: {', '.join(coherence_issues) or 'None'}",
                evidence={
                    "all_passed": False,
                    "total_confidence": total_confidence,
                    "total_energy": total_energy,
                    "coherence_issues": coherence_issues,
                },
                energy_cost=2.0,
                next_action="deny",
            )
        
        if coherence_issues:
            return StageResult(
                stage=ChainStage.ORACLE,
                passed=True,
                confidence=total_confidence * 0.9,  # Slightly reduce confidence
                reasoning=f"Oracle APPROVES with reservations: {', '.join(coherence_issues)}",
                evidence={
                    "all_passed": True,
                    "total_confidence": total_confidence,
                    "total_energy": total_energy,
                    "coherence_issues": coherence_issues,
                },
                energy_cost=2.0,
                next_action="approve_with_logging",
            )
        
        return StageResult(
            stage=ChainStage.ORACLE,
            passed=True,
            confidence=total_confidence,
            reasoning=f"Oracle APPROVES: All stages passed with high coherence. Total confidence: {total_confidence:.2f}",
            evidence={
                "all_passed": True,
                "total_confidence": total_confidence,
                "total_energy": total_energy,
                "coherence_issues": [],
            },
            energy_cost=2.0,
            next_action="approve",
        )
    
    def get_prompt(self, context: ChainContext) -> str:
        """Prompt for LLM-assisted meta-reasoning"""
        return f"""ORACLE META-REASONING

Review the entire verification chain for this passphrase attempt:

User: {context.user_id}
Input: "{context.input_text}"
Session: {context.session_id}

STAGE RESULTS:
{json.dumps(context.stage_results, indent=2, default=str)}

REASONING CHAIN:
{chr(10).join(context.reasoning_chain)}

ENERGY CONSUMED: {context.energy_consumed}

As the Oracle, perform meta-reasoning:
1. Is the reasoning chain coherent and complete?
2. Are there any red flags across stages that might have been missed?
3. What is your final confidence in this verification?

Think step by step, then give your final verdict: APPROVE, DENY, or ESCALATE."""


class PromptChainVerifier:
    """
    Main orchestrator for the prompt chain verification system.
    
    Runs input through the full chain:
    Lexical → Semantic → Intent → Oracle
    
    Each stage builds on the previous, creating an embedded
    verification chain that is very difficult to bypass.
    """
    
    def __init__(self, passphrase_hash: str):
        """
        Initialize the verifier with the expected passphrase hash.
        
        Args:
            passphrase_hash: SHA256 hash of the correct passphrase (lowercase, stripped)
        """
        self.passphrase_hash = passphrase_hash
        self.stages: Dict[ChainStage, ChainStageProcessor] = {
            ChainStage.LEXICAL: LexicalStage(),
            ChainStage.SEMANTIC: SemanticStage(),
            ChainStage.INTENT: IntentStage(),
            ChainStage.ORACLE: OracleStage(),
        }
        self.stage_order = [
            ChainStage.LEXICAL,
            ChainStage.SEMANTIC,
            ChainStage.INTENT,
            ChainStage.ORACLE,
        ]
    
    async def verify(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[VerificationOutcome, ChainContext]:
        """
        Run the full verification chain.
        
        Args:
            input_text: The passphrase attempt
            user_id: ID of the user attempting verification
            session_id: Current session ID
            metadata: Optional additional context
            
        Returns:
            Tuple of (outcome, context with full chain results)
        """
        context = ChainContext(
            user_id=user_id,
            session_id=session_id,
            input_text=input_text,
            expected_passphrase_hash=self.passphrase_hash,
            metadata=metadata or {},
        )
        
        logger.info(f"Starting prompt chain verification for user {user_id}")
        
        # Run through each stage
        for stage in self.stage_order:
            processor = self.stages[stage]
            
            try:
                result = await processor.process(context)
                
                # Update context with result
                context.stages_completed.append(stage.value)
                context.stage_results[stage.value] = {
                    "passed": result.passed,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "evidence": result.evidence,
                    "next_action": result.next_action,
                }
                context.reasoning_chain.append(
                    f"[{stage.value.upper()}] {result.reasoning}"
                )
                context.energy_consumed += result.energy_cost
                
                logger.info(f"Stage {stage.value}: passed={result.passed}, confidence={result.confidence:.2f}")
                
                # Early exit on failure (except for Oracle which we always run)
                if not result.passed and stage != ChainStage.ORACLE:
                    if result.next_action == "block_and_log":
                        return VerificationOutcome.FAIL, context
                    elif result.next_action == "challenge":
                        return VerificationOutcome.CHALLENGE, context
                    elif result.next_action == "escalate":
                        return VerificationOutcome.ESCALATE, context
                    else:
                        return VerificationOutcome.FAIL, context
                
            except Exception as e:
                logger.error(f"Error in stage {stage.value}: {e}")
                context.reasoning_chain.append(
                    f"[{stage.value.upper()}] ERROR: {str(e)}"
                )
                return VerificationOutcome.ESCALATE, context
        
        # Final outcome based on Oracle's decision
        oracle_result = context.stage_results.get(ChainStage.ORACLE.value, {})
        if oracle_result.get("passed", False):
            if oracle_result.get("next_action") == "approve_with_logging":
                logger.warning(f"Verification approved with reservations for user {user_id}")
            return VerificationOutcome.PASS, context
        else:
            return VerificationOutcome.FAIL, context
    
    @staticmethod
    def hash_passphrase(passphrase: str) -> str:
        """Hash a passphrase for storage/comparison"""
        return hashlib.sha256(passphrase.strip().lower().encode()).hexdigest()


# Export for use in other modules
import json  # For oracle prompt formatting

__all__ = [
    "PromptChainVerifier",
    "ChainContext",
    "StageResult",
    "VerificationOutcome",
    "ChainStage",
]
