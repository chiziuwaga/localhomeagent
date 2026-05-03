"""
Voice Verification and Command Module (P4 D2.1, D2.2)
Handles voice-based verification for high-risk actions and voice commands
"""

import os
import re
import hashlib
import hmac
import base64
import logging
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

logger = logging.getLogger(__name__)


class VoiceVerificationState(Enum):
    """States for voice verification flow"""
    PENDING = "pending"
    LISTENING = "listening"
    PROCESSING = "processing"
    VERIFIED = "verified"
    FAILED = "failed"
    TIMEOUT = "timeout"


class VoiceCommandCategory(Enum):
    """Categories of voice commands"""
    DEVICE_CONTROL = "device_control"
    INFORMATION = "information"
    SECURITY = "security"
    SETTINGS = "settings"
    COMMUNICATION = "communication"
    EMERGENCY = "emergency"


@dataclass
class VoiceCommand:
    """Represents a parsed voice command"""
    raw_text: str
    category: VoiceCommandCategory
    action: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    requires_verification: bool = False


@dataclass
class VoiceVerificationChallenge:
    """A challenge for voice verification"""
    challenge_id: str
    user_id: str
    phrase: str
    created_at: datetime
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    state: VoiceVerificationState = VoiceVerificationState.PENDING


class VoicePatterns:
    """Common voice command patterns"""
    
    # Device control patterns
    TURN_ON = re.compile(r"turn on (?:the )?(.+)", re.I)
    TURN_OFF = re.compile(r"turn off (?:the )?(.+)", re.I)
    SET_TO = re.compile(r"set (?:the )?(.+) to (.+)", re.I)
    DIM = re.compile(r"dim (?:the )?(.+)(?: to (\d+)%?)?", re.I)
    BRIGHTEN = re.compile(r"brighten (?:the )?(.+)", re.I)
    
    # Information patterns
    WHATS_THE = re.compile(r"what(?:'s| is) (?:the )?(.+)", re.I)
    SHOW_ME = re.compile(r"show me (?:the )?(.+)", re.I)
    STATUS = re.compile(r"(?:what is the )?status (?:of )?(?:the )?(.+)", re.I)
    
    # Security patterns
    LOCK = re.compile(r"lock (?:the )?(.+)", re.I)
    UNLOCK = re.compile(r"unlock (?:the )?(.+)", re.I)
    ARM = re.compile(r"arm (?:the )?(?:security|alarm)(?: system)?", re.I)
    DISARM = re.compile(r"disarm (?:the )?(?:security|alarm)(?: system)?", re.I)
    
    # Emergency patterns
    EMERGENCY = re.compile(r"(?:emergency|panic|help|911)", re.I)
    CALL = re.compile(r"call (?:for )?(.+)", re.I)


class VoiceVerificationManager:
    """Manages voice verification for high-risk actions"""
    
    # Phrases for verification challenges
    CHALLENGE_PHRASES = [
        "The quick brown fox jumps over the lazy dog",
        "Pack my box with five dozen liquor jugs",
        "How vexingly quick daft zebras jump",
        "The five boxing wizards jump quickly",
        "Sphinx of black quartz judge my vow",
        "Two driven jocks help fax my big quiz",
        "The jay pig fox and zebra quickly moved",
        "Watch Jeopardy Alex Trebek's fun TV quiz game"
    ]
    
    # Dynamic number phrases
    NUMBER_TEMPLATES = [
        "My code is {num1}-{num2}-{num3}",
        "Verify with numbers {num1} {num2} {num3}",
        "Security code: {num1} dash {num2} dash {num3}"
    ]
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.urandom(32).hex()
        self.active_challenges: Dict[str, VoiceVerificationChallenge] = {}
        self.verification_history: List[Dict[str, Any]] = []
        self.challenge_timeout = 60  # seconds
        
    def generate_challenge(self, user_id: str, action: str) -> VoiceVerificationChallenge:
        """Generate a new voice verification challenge"""
        import random
        
        # Generate challenge ID
        challenge_id = hashlib.sha256(
            f"{user_id}{action}{datetime.now().isoformat()}{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        
        # Select phrase type based on security level
        if self._is_critical_action(action):
            # Use dynamic number phrase for critical actions
            template = random.choice(self.NUMBER_TEMPLATES)
            nums = [str(random.randint(0, 9)) for _ in range(3)]
            phrase = template.format(num1=nums[0], num2=nums[1], num3=nums[2])
        else:
            # Use standard phrase for normal verification
            phrase = random.choice(self.CHALLENGE_PHRASES)
        
        challenge = VoiceVerificationChallenge(
            challenge_id=challenge_id,
            user_id=user_id,
            phrase=phrase,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.challenge_timeout)
        )
        
        self.active_challenges[challenge_id] = challenge
        logger.info(f"Generated voice challenge {challenge_id} for user {user_id}")
        
        return challenge
    
    def verify_response(
        self,
        challenge_id: str,
        spoken_text: str,
        audio_features: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """Verify a spoken response against a challenge"""
        
        challenge = self.active_challenges.get(challenge_id)
        
        if not challenge:
            return False, "Challenge not found or expired"
        
        if datetime.now() > challenge.expires_at:
            challenge.state = VoiceVerificationState.TIMEOUT
            del self.active_challenges[challenge_id]
            return False, "Challenge timed out"
        
        challenge.attempts += 1
        challenge.state = VoiceVerificationState.PROCESSING
        
        # Normalize texts for comparison
        expected = self._normalize_text(challenge.phrase)
        spoken = self._normalize_text(spoken_text)
        
        # Calculate similarity
        similarity = self._calculate_similarity(expected, spoken)
        
        # For critical actions, require higher similarity
        threshold = 0.9 if self._is_critical_action_challenge(challenge) else 0.8
        
        if similarity >= threshold:
            challenge.state = VoiceVerificationState.VERIFIED
            del self.active_challenges[challenge_id]
            self._log_verification(challenge, True, similarity)
            return True, "Voice verification successful"
        
        if challenge.attempts >= challenge.max_attempts:
            challenge.state = VoiceVerificationState.FAILED
            del self.active_challenges[challenge_id]
            self._log_verification(challenge, False, similarity)
            return False, "Maximum attempts exceeded"
        
        remaining = challenge.max_attempts - challenge.attempts
        return False, f"Phrase did not match. {remaining} attempts remaining"
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Convert to lowercase, remove punctuation, normalize spaces
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    
    def _calculate_similarity(self, expected: str, spoken: str) -> float:
        """Calculate similarity between expected and spoken text"""
        # Simple word-based similarity (Jaccard index)
        expected_words = set(expected.split())
        spoken_words = set(spoken.split())
        
        if not expected_words:
            return 0.0
        
        intersection = expected_words & spoken_words
        union = expected_words | spoken_words
        
        return len(intersection) / len(union) if union else 0.0
    
    def _is_critical_action(self, action: str) -> bool:
        """Check if action requires enhanced verification"""
        critical_actions = [
            "unlock_door", "disarm_alarm", "delete_data",
            "grant_access", "emergency_override", "payment"
        ]
        return action.lower() in critical_actions
    
    def _is_critical_action_challenge(self, challenge: VoiceVerificationChallenge) -> bool:
        """Check if challenge is for critical action (has numbers)"""
        return any(template.split()[0] in challenge.phrase 
                   for template in ["My", "Verify", "Security"])
    
    def _log_verification(
        self,
        challenge: VoiceVerificationChallenge,
        success: bool,
        similarity: float
    ):
        """Log verification attempt"""
        self.verification_history.append({
            "challenge_id": challenge.challenge_id,
            "user_id": challenge.user_id,
            "success": success,
            "similarity": similarity,
            "attempts": challenge.attempts,
            "timestamp": datetime.now().isoformat()
        })


class VoiceCommandProcessor:
    """Processes and routes voice commands"""
    
    # Commands that require voice verification
    HIGH_RISK_COMMANDS = [
        ("security", "unlock"),
        ("security", "disarm"),
        ("device_control", "unlock"),
        ("settings", "delete"),
        ("settings", "reset"),
        ("emergency", "override")
    ]
    
    def __init__(self, verification_manager: Optional[VoiceVerificationManager] = None):
        self.verification_manager = verification_manager or VoiceVerificationManager()
        self.command_history: List[VoiceCommand] = []
        self.aliases: Dict[str, str] = {}  # Device aliases
        
    def parse_command(self, text: str) -> Optional[VoiceCommand]:
        """Parse raw text into a structured voice command"""
        text = text.strip()
        
        if not text:
            return None
        
        # Try each pattern category
        command = self._try_device_control(text)
        if not command:
            command = self._try_information(text)
        if not command:
            command = self._try_security(text)
        if not command:
            command = self._try_emergency(text)
        
        if command:
            # Check if verification is required
            command.requires_verification = self._requires_verification(command)
            self.command_history.append(command)
        
        return command
    
    def _try_device_control(self, text: str) -> Optional[VoiceCommand]:
        """Try to parse as device control command"""
        
        # Turn on
        match = VoicePatterns.TURN_ON.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.DEVICE_CONTROL,
                action="turn_on",
                target=self._resolve_alias(match.group(1)),
                confidence=0.9
            )
        
        # Turn off
        match = VoicePatterns.TURN_OFF.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.DEVICE_CONTROL,
                action="turn_off",
                target=self._resolve_alias(match.group(1)),
                confidence=0.9
            )
        
        # Set to
        match = VoicePatterns.SET_TO.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.DEVICE_CONTROL,
                action="set",
                target=self._resolve_alias(match.group(1)),
                parameters={"value": match.group(2)},
                confidence=0.85
            )
        
        # Dim
        match = VoicePatterns.DIM.match(text)
        if match:
            level = int(match.group(2)) if match.group(2) else 50
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.DEVICE_CONTROL,
                action="dim",
                target=self._resolve_alias(match.group(1)),
                parameters={"level": level},
                confidence=0.85
            )
        
        return None
    
    def _try_information(self, text: str) -> Optional[VoiceCommand]:
        """Try to parse as information query"""
        
        match = VoicePatterns.WHATS_THE.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.INFORMATION,
                action="query",
                target=match.group(1),
                confidence=0.85
            )
        
        match = VoicePatterns.STATUS.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.INFORMATION,
                action="status",
                target=self._resolve_alias(match.group(1)),
                confidence=0.9
            )
        
        return None
    
    def _try_security(self, text: str) -> Optional[VoiceCommand]:
        """Try to parse as security command"""
        
        match = VoicePatterns.LOCK.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.SECURITY,
                action="lock",
                target=self._resolve_alias(match.group(1)),
                confidence=0.9,
                requires_verification=False  # Lock doesn't need verification
            )
        
        match = VoicePatterns.UNLOCK.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.SECURITY,
                action="unlock",
                target=self._resolve_alias(match.group(1)),
                confidence=0.9,
                requires_verification=True  # Unlock needs verification
            )
        
        match = VoicePatterns.DISARM.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.SECURITY,
                action="disarm",
                target="alarm_system",
                confidence=0.9,
                requires_verification=True
            )
        
        match = VoicePatterns.ARM.match(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.SECURITY,
                action="arm",
                target="alarm_system",
                confidence=0.9
            )
        
        return None
    
    def _try_emergency(self, text: str) -> Optional[VoiceCommand]:
        """Try to parse as emergency command"""
        
        match = VoicePatterns.EMERGENCY.search(text)
        if match:
            return VoiceCommand(
                raw_text=text,
                category=VoiceCommandCategory.EMERGENCY,
                action="panic",
                confidence=0.95
            )
        
        return None
    
    def _resolve_alias(self, name: str) -> str:
        """Resolve device alias to actual name"""
        name = name.lower().strip()
        return self.aliases.get(name, name)
    
    def _requires_verification(self, command: VoiceCommand) -> bool:
        """Check if command requires voice verification"""
        return (command.category.value, command.action) in [
            (cat, act) for cat, act in self.HIGH_RISK_COMMANDS
        ]
    
    def add_alias(self, alias: str, device_name: str):
        """Add a device alias"""
        self.aliases[alias.lower()] = device_name.lower()
    
    def get_supported_commands(self) -> Dict[str, List[str]]:
        """Get list of supported commands by category"""
        return {
            "device_control": [
                "turn on [device]",
                "turn off [device]",
                "set [device] to [value]",
                "dim [device] to [level]%",
                "brighten [device]"
            ],
            "information": [
                "what's the [metric]",
                "show me [info]",
                "status of [device]"
            ],
            "security": [
                "lock [door]",
                "unlock [door] (requires verification)",
                "arm security",
                "disarm security (requires verification)"
            ],
            "emergency": [
                "emergency",
                "panic",
                "help"
            ]
        }


class VoiceFeedbackGenerator:
    """Generates voice feedback responses"""
    
    CONFIRMATIONS = {
        "turn_on": "Turning on {target}",
        "turn_off": "Turning off {target}",
        "set": "Setting {target} to {value}",
        "dim": "Dimming {target} to {level} percent",
        "lock": "Locking {target}",
        "unlock": "Unlocking {target}",
        "arm": "Arming the security system",
        "disarm": "Disarming the security system",
        "query": "The {target} is {value}",
        "status": "The {target} is currently {status}"
    }
    
    ERRORS = {
        "not_found": "I couldn't find a device called {target}",
        "not_supported": "That action is not supported for {target}",
        "verification_required": "This action requires voice verification. Please say: {phrase}",
        "verification_failed": "Voice verification failed. Please try again",
        "permission_denied": "You don't have permission to {action}",
        "offline": "The {target} appears to be offline"
    }
    
    def generate_confirmation(self, command: VoiceCommand, result: Dict[str, Any]) -> str:
        """Generate confirmation message for successful command"""
        template = self.CONFIRMATIONS.get(command.action, "Command executed")
        
        return template.format(
            target=command.target or "device",
            value=command.parameters.get("value", ""),
            level=command.parameters.get("level", ""),
            status=result.get("status", "")
        )
    
    def generate_error(self, error_type: str, **kwargs) -> str:
        """Generate error message"""
        template = self.ERRORS.get(error_type, "An error occurred")
        return template.format(**kwargs)


# API endpoint handlers
def create_voice_routes():
    """Create FastAPI routes for voice functionality"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/api/voice", tags=["voice"])
    
    voice_processor = VoiceCommandProcessor()
    feedback_generator = VoiceFeedbackGenerator()
    
    class VoiceInput(BaseModel):
        text: str
        user_id: str
    
    class VerificationResponse(BaseModel):
        challenge_id: str
        phrase: str
        timeout_seconds: int
    
    class VerificationAttempt(BaseModel):
        challenge_id: str
        spoken_text: str
    
    @router.post("/command")
    async def process_voice_command(input: VoiceInput):
        """Process a voice command"""
        command = voice_processor.parse_command(input.text)
        
        if not command:
            return {
                "success": False,
                "message": "I didn't understand that command",
                "suggestions": voice_processor.get_supported_commands()
            }
        
        if command.requires_verification:
            # Generate verification challenge
            challenge = voice_processor.verification_manager.generate_challenge(
                input.user_id,
                command.action
            )
            
            return {
                "success": True,
                "requires_verification": True,
                "challenge": {
                    "id": challenge.challenge_id,
                    "phrase": challenge.phrase,
                    "timeout_seconds": 60
                },
                "command": {
                    "action": command.action,
                    "target": command.target,
                    "category": command.category.value
                }
            }
        
        # Execute command (would connect to actual device control)
        return {
            "success": True,
            "command": {
                "action": command.action,
                "target": command.target,
                "category": command.category.value
            },
            "message": feedback_generator.generate_confirmation(command, {})
        }
    
    @router.post("/verify")
    async def verify_voice(attempt: VerificationAttempt):
        """Verify a voice challenge"""
        success, message = voice_processor.verification_manager.verify_response(
            attempt.challenge_id,
            attempt.spoken_text
        )
        
        return {
            "success": success,
            "message": message
        }
    
    @router.get("/commands")
    async def get_supported_commands():
        """Get list of supported voice commands"""
        return voice_processor.get_supported_commands()
    
    @router.post("/alias")
    async def add_device_alias(alias: str, device: str):
        """Add a device alias"""
        voice_processor.add_alias(alias, device)
        return {"success": True, "message": f"Alias '{alias}' added for '{device}'"}
    
    return router
