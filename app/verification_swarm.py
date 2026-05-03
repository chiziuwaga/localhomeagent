"""
Agentic Swarm for Passphrase Verification (P3/N1.1)

This module implements a multi-agent swarm architecture where specialized
agents collaborate to verify passphrase attempts. The swarm provides
defense-in-depth through agent diversity and cross-validation.

Architecture:
                    ┌─────────────────────┐
                    │   SwarmOrchestrator │
                    │   (Energy Budget)   │
                    └─────────┬───────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  VerifierAgent  │  │ ChallengerAgent │  │  AuditorAgent   │
│ (Pattern Match) │  │ (Adversarial)   │  │ (Logging/Audit) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                    ┌─────────────────────┐
                    │   ConsensusEngine   │
                    │ (Byzantine Fault    │
                    │  Tolerant Voting)   │
                    └─────────────────────┘

Agents:
- VerifierAgent: Primary pattern matching and hash verification
- ChallengerAgent: Adversarial testing, tries to find bypasses
- AuditorAgent: Logging, compliance, and historical pattern analysis

The swarm requires 2/3 consensus for high-risk actions.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import hashlib
import json

from .prompt_chains import (
    PromptChainVerifier,
    ChainContext,
    VerificationOutcome,
    ChainStage,
)
from .energy_model import EnergyModel, EnergyLevel, UserContext, ActionRequest

logger = logging.getLogger(__name__)


class AgentVote(Enum):
    """Possible votes from swarm agents"""
    APPROVE = "approve"
    DENY = "deny"
    ABSTAIN = "abstain"
    CHALLENGE = "challenge"


@dataclass
class SwarmVote:
    """A vote from a swarm agent"""
    agent_id: str
    agent_type: str
    vote: AgentVote
    confidence: float
    reasoning: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SwarmConsensus:
    """Result of swarm consensus"""
    outcome: VerificationOutcome
    votes: List[SwarmVote]
    total_approve: int
    total_deny: int
    total_abstain: int
    total_challenge: int
    consensus_achieved: bool
    reasoning: str
    energy_consumed: float


@dataclass
class SwarmContext:
    """Context for swarm verification"""
    user_id: str
    session_id: str
    input_text: str
    passphrase_hash: str
    user_context: Optional[UserContext] = None
    chain_context: Optional[ChainContext] = None
    votes: List[SwarmVote] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class SwarmAgent(ABC):
    """Abstract base class for swarm agents"""
    
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        energy_budget: float = 20.0,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.energy_budget = energy_budget
        self.energy_consumed = 0.0
        self.history: List[Dict[str, Any]] = []
    
    @abstractmethod
    async def evaluate(self, context: SwarmContext) -> SwarmVote:
        """Evaluate the passphrase attempt and cast a vote"""
        pass
    
    def consume_energy(self, amount: float) -> bool:
        """Consume energy from budget"""
        if self.energy_consumed + amount > self.energy_budget:
            return False
        self.energy_consumed += amount
        return True
    
    def reset_energy(self):
        """Reset energy for new verification round"""
        self.energy_consumed = 0.0
    
    def log_evaluation(self, vote: SwarmVote):
        """Log evaluation for historical analysis"""
        self.history.append({
            "vote": vote.vote.value,
            "confidence": vote.confidence,
            "timestamp": vote.timestamp.isoformat(),
            "reasoning": vote.reasoning,
        })
        # Keep only last 100 evaluations
        if len(self.history) > 100:
            self.history = self.history[-100:]


class VerifierAgent(SwarmAgent):
    """
    Primary verification agent that performs pattern matching
    and hash verification. Uses the prompt chain for deep analysis.
    """
    
    def __init__(self):
        super().__init__(
            agent_id="verifier-001",
            agent_type="verifier",
            energy_budget=25.0,
        )
        self.prompt_chain_verifier: Optional[PromptChainVerifier] = None
    
    async def evaluate(self, context: SwarmContext) -> SwarmVote:
        """Run primary verification checks"""
        self.reset_energy()
        self.consume_energy(5.0)
        
        # Initialize prompt chain verifier with the hash
        self.prompt_chain_verifier = PromptChainVerifier(context.passphrase_hash)
        
        # Run the full prompt chain
        outcome, chain_context = await self.prompt_chain_verifier.verify(
            input_text=context.input_text,
            user_id=context.user_id,
            session_id=context.session_id,
            metadata=context.metadata,
        )
        
        # Store chain context in swarm context for other agents
        context.chain_context = chain_context
        
        # Energy from chain
        self.consume_energy(chain_context.energy_consumed)
        
        # Map outcome to vote
        if outcome == VerificationOutcome.PASS:
            vote = AgentVote.APPROVE
        elif outcome == VerificationOutcome.CHALLENGE:
            vote = AgentVote.CHALLENGE
        elif outcome == VerificationOutcome.ESCALATE:
            vote = AgentVote.ABSTAIN
        else:
            vote = AgentVote.DENY
        
        # Calculate confidence from chain results
        oracle_result = chain_context.stage_results.get(ChainStage.ORACLE.value, {})
        confidence = oracle_result.get("confidence", 0.5)
        
        swarm_vote = SwarmVote(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            vote=vote,
            confidence=confidence,
            reasoning=f"Prompt chain result: {outcome.value}. " + 
                     "\n".join(chain_context.reasoning_chain[-3:]),
            evidence={
                "chain_outcome": outcome.value,
                "stages_completed": chain_context.stages_completed,
                "energy_consumed": chain_context.energy_consumed,
            },
        )
        
        self.log_evaluation(swarm_vote)
        return swarm_vote


class ChallengerAgent(SwarmAgent):
    """
    Adversarial agent that tries to find weaknesses in the verification.
    It assumes a hostile stance and looks for potential bypasses.
    """
    
    # Known attack patterns the challenger looks for
    ATTACK_PATTERNS = [
        ("prompt_injection", [
            "ignore", "forget", "system", "admin", "bypass",
            "override", "sudo", "root", "debug"
        ]),
        ("encoding_attack", [
            "%", "\\x", "\\u", "&#", "&lt;", "&gt;"
        ]),
        ("timing_attack", [
            # Checked through behavioral analysis
        ]),
        ("replay_attack", [
            # Checked through session/timestamp analysis
        ]),
    ]
    
    def __init__(self):
        super().__init__(
            agent_id="challenger-001",
            agent_type="challenger",
            energy_budget=15.0,
        )
        self.attack_attempts: List[Dict[str, Any]] = []
    
    async def evaluate(self, context: SwarmContext) -> SwarmVote:
        """Adversarially evaluate the passphrase attempt"""
        self.reset_energy()
        self.consume_energy(3.0)
        
        issues_found = []
        risk_score = 0.0
        
        input_text = context.input_text
        
        # Check 1: Known attack patterns
        for attack_type, patterns in self.ATTACK_PATTERNS:
            for pattern in patterns:
                if pattern.lower() in input_text.lower():
                    issues_found.append(f"{attack_type}: found '{pattern}'")
                    risk_score += 20.0
        
        self.consume_energy(2.0)
        
        # Check 2: Timing analysis (suspicious if too fast or too slow)
        if context.chain_context:
            chain_time = context.chain_context.energy_consumed  # Proxy for time
            if chain_time < 1.0:
                issues_found.append("timing: suspiciously fast (automated?)")
                risk_score += 15.0
            elif chain_time > 50.0:
                issues_found.append("timing: unusually slow (brute force?)")
                risk_score += 10.0
        
        # Check 3: Session replay detection
        session_key = hashlib.md5(
            f"{context.session_id}:{context.input_text}".encode()
        ).hexdigest()[:8]
        
        recent_attempts = [
            a for a in self.attack_attempts
            if datetime.now() - datetime.fromisoformat(a["timestamp"]) < timedelta(minutes=5)
        ]
        
        if any(a["session_key"] == session_key for a in recent_attempts):
            issues_found.append("replay: duplicate attempt within 5 minutes")
            risk_score += 30.0
        
        self.attack_attempts.append({
            "session_key": session_key,
            "timestamp": datetime.now().isoformat(),
            "user_id": context.user_id,
        })
        
        # Keep only last 100 attempts
        if len(self.attack_attempts) > 100:
            self.attack_attempts = self.attack_attempts[-100:]
        
        self.consume_energy(3.0)
        
        # Check 4: Cross-validate with verifier's chain results
        if context.chain_context:
            # Look for inconsistencies in chain results
            lexical = context.chain_context.stage_results.get("lexical", {})
            semantic = context.chain_context.stage_results.get("semantic", {})
            
            # If lexical passed but semantic failed, might be sophisticated attack
            if lexical.get("passed") and not semantic.get("passed"):
                issues_found.append("chain_inconsistency: lexical passed but semantic failed")
                risk_score += 25.0
        
        # Determine vote based on risk score
        if risk_score >= 50.0:
            vote = AgentVote.DENY
            confidence = min(0.95, 0.5 + risk_score / 100)
        elif risk_score >= 25.0:
            vote = AgentVote.CHALLENGE
            confidence = 0.7
        elif risk_score >= 10.0:
            vote = AgentVote.ABSTAIN
            confidence = 0.6
        else:
            # No issues found, but challenger is naturally skeptical
            vote = AgentVote.APPROVE
            confidence = 0.75  # Never 100% confident
        
        reasoning = f"Adversarial analysis: risk_score={risk_score:.1f}. "
        if issues_found:
            reasoning += f"Issues: {', '.join(issues_found)}"
        else:
            reasoning += "No attack patterns detected."
        
        swarm_vote = SwarmVote(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            vote=vote,
            confidence=confidence,
            reasoning=reasoning,
            evidence={
                "risk_score": risk_score,
                "issues_found": issues_found,
                "recent_attempts": len(recent_attempts),
            },
        )
        
        self.log_evaluation(swarm_vote)
        return swarm_vote


class AuditorAgent(SwarmAgent):
    """
    Audit and compliance agent that logs all verification attempts
    and performs historical pattern analysis.
    """
    
    def __init__(self):
        super().__init__(
            agent_id="auditor-001",
            agent_type="auditor",
            energy_budget=10.0,
        )
        self.audit_log: List[Dict[str, Any]] = []
        self.user_patterns: Dict[str, Dict[str, Any]] = {}
    
    async def evaluate(self, context: SwarmContext) -> SwarmVote:
        """Evaluate from audit/compliance perspective"""
        self.reset_energy()
        self.consume_energy(2.0)
        
        issues = []
        risk_score = 0.0
        
        user_id = context.user_id
        
        # Get or create user pattern tracking
        if user_id not in self.user_patterns:
            self.user_patterns[user_id] = {
                "attempt_count": 0,
                "success_count": 0,
                "fail_count": 0,
                "last_attempt": None,
                "typical_hours": set(),
                "known_devices": set(),
            }
        
        user_pattern = self.user_patterns[user_id]
        user_pattern["attempt_count"] += 1
        
        # Check 1: Rate limiting (too many attempts)
        if user_pattern["attempt_count"] > 10:
            window_attempts = len([
                a for a in self.audit_log
                if a["user_id"] == user_id and
                datetime.now() - datetime.fromisoformat(a["timestamp"]) < timedelta(hours=1)
            ])
            if window_attempts > 5:
                issues.append(f"rate_limit: {window_attempts} attempts in last hour")
                risk_score += 40.0
        
        self.consume_energy(2.0)
        
        # Check 2: Unusual time of day
        current_hour = context.timestamp.hour
        if user_pattern["typical_hours"] and current_hour not in user_pattern["typical_hours"]:
            issues.append(f"unusual_hour: {current_hour} not in typical hours")
            risk_score += 15.0
        else:
            user_pattern["typical_hours"].add(current_hour)
        
        # Check 3: Failure pattern (many recent failures)
        recent_failures = len([
            a for a in self.audit_log
            if a["user_id"] == user_id and
            a["outcome"] == "fail" and
            datetime.now() - datetime.fromisoformat(a["timestamp"]) < timedelta(hours=24)
        ])
        if recent_failures >= 3:
            issues.append(f"failure_pattern: {recent_failures} failures in 24h")
            risk_score += 25.0
        
        self.consume_energy(2.0)
        
        # Check 4: Cross-reference with chain results
        chain_outcome = None
        if context.chain_context:
            oracle = context.chain_context.stage_results.get("oracle", {})
            chain_passed = oracle.get("passed", False)
            chain_outcome = "pass" if chain_passed else "fail"
        
        # Determine vote based on audit analysis
        if risk_score >= 40.0:
            vote = AgentVote.CHALLENGE
            confidence = 0.8
        elif risk_score >= 20.0:
            vote = AgentVote.ABSTAIN
            confidence = 0.6
        else:
            # No audit concerns, defer to other agents
            vote = AgentVote.ABSTAIN
            confidence = 0.5
        
        reasoning = f"Audit analysis: risk_score={risk_score:.1f}. "
        if issues:
            reasoning += f"Issues: {', '.join(issues)}"
        else:
            reasoning += "No compliance concerns."
        
        # Log this attempt
        self.audit_log.append({
            "user_id": user_id,
            "session_id": context.session_id,
            "timestamp": context.timestamp.isoformat(),
            "outcome": chain_outcome or "pending",
            "risk_score": risk_score,
            "issues": issues,
        })
        
        # Keep only last 1000 entries
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
        
        swarm_vote = SwarmVote(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            vote=vote,
            confidence=confidence,
            reasoning=reasoning,
            evidence={
                "risk_score": risk_score,
                "issues": issues,
                "user_attempt_count": user_pattern["attempt_count"],
                "recent_failures": recent_failures,
            },
        )
        
        self.log_evaluation(swarm_vote)
        return swarm_vote
    
    def update_outcome(self, user_id: str, success: bool):
        """Update user patterns after verification completes"""
        if user_id in self.user_patterns:
            if success:
                self.user_patterns[user_id]["success_count"] += 1
            else:
                self.user_patterns[user_id]["fail_count"] += 1


class ConsensusEngine:
    """
    Byzantine Fault Tolerant consensus engine.
    Requires 2/3 majority for high-risk actions.
    """
    
    def __init__(self, quorum_threshold: float = 0.67):
        self.quorum_threshold = quorum_threshold
    
    def calculate_consensus(
        self,
        votes: List[SwarmVote],
        energy_consumed: float,
    ) -> SwarmConsensus:
        """Calculate consensus from swarm votes"""
        
        total_approve = sum(1 for v in votes if v.vote == AgentVote.APPROVE)
        total_deny = sum(1 for v in votes if v.vote == AgentVote.DENY)
        total_abstain = sum(1 for v in votes if v.vote == AgentVote.ABSTAIN)
        total_challenge = sum(1 for v in votes if v.vote == AgentVote.CHALLENGE)
        
        total_votes = len(votes) - total_abstain  # Abstains don't count
        
        # If any agent votes DENY with high confidence, respect it
        high_confidence_denies = [
            v for v in votes
            if v.vote == AgentVote.DENY and v.confidence >= 0.85
        ]
        if high_confidence_denies:
            return SwarmConsensus(
                outcome=VerificationOutcome.FAIL,
                votes=votes,
                total_approve=total_approve,
                total_deny=total_deny,
                total_abstain=total_abstain,
                total_challenge=total_challenge,
                consensus_achieved=True,
                reasoning=f"High-confidence DENY from {len(high_confidence_denies)} agent(s): " +
                         "; ".join(v.reasoning for v in high_confidence_denies),
                energy_consumed=energy_consumed,
            )
        
        # If any agent requests challenge, honor it
        if total_challenge > 0:
            return SwarmConsensus(
                outcome=VerificationOutcome.CHALLENGE,
                votes=votes,
                total_approve=total_approve,
                total_deny=total_deny,
                total_abstain=total_abstain,
                total_challenge=total_challenge,
                consensus_achieved=True,
                reasoning=f"Challenge requested by {total_challenge} agent(s)",
                energy_consumed=energy_consumed,
            )
        
        # Check for quorum
        if total_votes == 0:
            return SwarmConsensus(
                outcome=VerificationOutcome.ESCALATE,
                votes=votes,
                total_approve=total_approve,
                total_deny=total_deny,
                total_abstain=total_abstain,
                total_challenge=total_challenge,
                consensus_achieved=False,
                reasoning="All agents abstained, escalating to human review",
                energy_consumed=energy_consumed,
            )
        
        approve_ratio = total_approve / total_votes if total_votes > 0 else 0
        deny_ratio = total_deny / total_votes if total_votes > 0 else 0
        
        # Calculate weighted confidence
        approve_confidence = sum(
            v.confidence for v in votes if v.vote == AgentVote.APPROVE
        ) / max(total_approve, 1)
        
        deny_confidence = sum(
            v.confidence for v in votes if v.vote == AgentVote.DENY
        ) / max(total_deny, 1)
        
        # Determine outcome
        if approve_ratio >= self.quorum_threshold and approve_confidence >= 0.7:
            return SwarmConsensus(
                outcome=VerificationOutcome.PASS,
                votes=votes,
                total_approve=total_approve,
                total_deny=total_deny,
                total_abstain=total_abstain,
                total_challenge=total_challenge,
                consensus_achieved=True,
                reasoning=f"Quorum achieved: {approve_ratio:.0%} approve with {approve_confidence:.0%} confidence",
                energy_consumed=energy_consumed,
            )
        elif deny_ratio >= self.quorum_threshold:
            return SwarmConsensus(
                outcome=VerificationOutcome.FAIL,
                votes=votes,
                total_approve=total_approve,
                total_deny=total_deny,
                total_abstain=total_abstain,
                total_challenge=total_challenge,
                consensus_achieved=True,
                reasoning=f"Denial quorum: {deny_ratio:.0%} deny",
                energy_consumed=energy_consumed,
            )
        else:
            # No clear consensus, challenge for additional verification
            return SwarmConsensus(
                outcome=VerificationOutcome.CHALLENGE,
                votes=votes,
                total_approve=total_approve,
                total_deny=total_deny,
                total_abstain=total_abstain,
                total_challenge=total_challenge,
                consensus_achieved=False,
                reasoning=f"No consensus: approve={approve_ratio:.0%}, deny={deny_ratio:.0%}",
                energy_consumed=energy_consumed,
            )


class PassphraseSwarm:
    """
    Main orchestrator for the passphrase verification swarm.
    
    Coordinates multiple specialized agents to verify passphrase
    attempts with defense-in-depth.
    """
    
    def __init__(self, passphrase_hash: str):
        """
        Initialize the swarm.
        
        Args:
            passphrase_hash: SHA256 hash of the correct passphrase
        """
        self.passphrase_hash = passphrase_hash
        
        # Initialize agents
        self.agents: List[SwarmAgent] = [
            VerifierAgent(),
            ChallengerAgent(),
            AuditorAgent(),
        ]
        
        # Initialize consensus engine
        self.consensus_engine = ConsensusEngine(quorum_threshold=0.67)
        
        # Swarm statistics
        self.total_verifications = 0
        self.total_passes = 0
        self.total_fails = 0
        self.total_challenges = 0
    
    async def verify(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        user_context: Optional[UserContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SwarmConsensus:
        """
        Run the full swarm verification.
        
        Args:
            input_text: The passphrase attempt
            user_id: ID of the user
            session_id: Current session ID
            user_context: Optional user context for energy model
            metadata: Optional additional context
            
        Returns:
            SwarmConsensus with the verification result
        """
        self.total_verifications += 1
        
        context = SwarmContext(
            user_id=user_id,
            session_id=session_id,
            input_text=input_text,
            passphrase_hash=self.passphrase_hash,
            user_context=user_context,
            metadata=metadata or {},
        )
        
        logger.info(f"Starting swarm verification for user {user_id}")
        
        # Collect votes from all agents (in parallel)
        votes = []
        total_energy = 0.0
        
        tasks = [agent.evaluate(context) for agent in self.agents]
        vote_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(vote_results):
            if isinstance(result, Exception):
                logger.error(f"Agent {self.agents[i].agent_id} failed: {result}")
                # Create abstain vote for failed agent
                votes.append(SwarmVote(
                    agent_id=self.agents[i].agent_id,
                    agent_type=self.agents[i].agent_type,
                    vote=AgentVote.ABSTAIN,
                    confidence=0.0,
                    reasoning=f"Agent error: {str(result)}",
                ))
            else:
                votes.append(result)
                total_energy += self.agents[i].energy_consumed
        
        context.votes = votes
        
        # Calculate consensus
        consensus = self.consensus_engine.calculate_consensus(votes, total_energy)
        
        # Update statistics
        if consensus.outcome == VerificationOutcome.PASS:
            self.total_passes += 1
        elif consensus.outcome == VerificationOutcome.FAIL:
            self.total_fails += 1
        else:
            self.total_challenges += 1
        
        # Update auditor with final outcome
        for agent in self.agents:
            if isinstance(agent, AuditorAgent):
                agent.update_outcome(
                    user_id,
                    consensus.outcome == VerificationOutcome.PASS
                )
        
        logger.info(
            f"Swarm verification complete: {consensus.outcome.value} "
            f"(approve={consensus.total_approve}, deny={consensus.total_deny}, "
            f"challenge={consensus.total_challenge})"
        )
        
        return consensus
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get swarm statistics"""
        return {
            "total_verifications": self.total_verifications,
            "total_passes": self.total_passes,
            "total_fails": self.total_fails,
            "total_challenges": self.total_challenges,
            "pass_rate": self.total_passes / max(self.total_verifications, 1),
            "agents": [
                {
                    "id": agent.agent_id,
                    "type": agent.agent_type,
                    "evaluations": len(agent.history),
                }
                for agent in self.agents
            ],
        }
    
    @staticmethod
    def hash_passphrase(passphrase: str) -> str:
        """Hash a passphrase for storage/comparison"""
        return hashlib.sha256(passphrase.strip().lower().encode()).hexdigest()


# Factory function for easy instantiation
def create_passphrase_swarm(passphrase: str) -> PassphraseSwarm:
    """
    Create a passphrase verification swarm.
    
    Args:
        passphrase: The correct passphrase (will be hashed)
        
    Returns:
        Configured PassphraseSwarm instance
    """
    passphrase_hash = PassphraseSwarm.hash_passphrase(passphrase)
    return PassphraseSwarm(passphrase_hash)


__all__ = [
    "PassphraseSwarm",
    "SwarmConsensus",
    "SwarmVote",
    "AgentVote",
    "create_passphrase_swarm",
]
