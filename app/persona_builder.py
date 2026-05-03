"""
Custom Persona Builder (P4 D2.4)
Create and manage custom AI personas for the home assistant
"""

import os
import json
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import secrets

logger = logging.getLogger(__name__)


class PersonalityTrait(Enum):
    """Personality traits for personas"""
    FORMAL = "formal"
    CASUAL = "casual"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    HUMOROUS = "humorous"
    SERIOUS = "serious"
    EMPATHETIC = "empathetic"
    DIRECT = "direct"
    VERBOSE = "verbose"
    CONCISE = "concise"


class VoiceStyle(Enum):
    """Voice styles for text-to-speech"""
    NEUTRAL = "neutral"
    WARM = "warm"
    ENERGETIC = "energetic"
    CALM = "calm"
    AUTHORITATIVE = "authoritative"
    CHEERFUL = "cheerful"


class InteractionStyle(Enum):
    """How the persona interacts"""
    PROACTIVE = "proactive"  # Offers suggestions unprompted
    REACTIVE = "reactive"    # Only responds when asked
    BALANCED = "balanced"    # Mix of both


@dataclass
class PersonaGreetings:
    """Custom greetings for different times and situations"""
    morning: List[str] = field(default_factory=list)
    afternoon: List[str] = field(default_factory=list)
    evening: List[str] = field(default_factory=list)
    night: List[str] = field(default_factory=list)
    welcome_home: List[str] = field(default_factory=list)
    goodbye: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, List[str]]:
        return {
            "morning": self.morning,
            "afternoon": self.afternoon,
            "evening": self.evening,
            "night": self.night,
            "welcome_home": self.welcome_home,
            "goodbye": self.goodbye
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, List[str]]) -> "PersonaGreetings":
        return cls(
            morning=data.get("morning", []),
            afternoon=data.get("afternoon", []),
            evening=data.get("evening", []),
            night=data.get("night", []),
            welcome_home=data.get("welcome_home", []),
            goodbye=data.get("goodbye", [])
        )


@dataclass
class PersonaResponses:
    """Custom response templates"""
    acknowledgement: List[str] = field(default_factory=list)
    confirmation: List[str] = field(default_factory=list)
    apology: List[str] = field(default_factory=list)
    clarification: List[str] = field(default_factory=list)
    completion: List[str] = field(default_factory=list)
    error: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, List[str]]:
        return {
            "acknowledgement": self.acknowledgement,
            "confirmation": self.confirmation,
            "apology": self.apology,
            "clarification": self.clarification,
            "completion": self.completion,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, List[str]]) -> "PersonaResponses":
        return cls(
            acknowledgement=data.get("acknowledgement", []),
            confirmation=data.get("confirmation", []),
            apology=data.get("apology", []),
            clarification=data.get("clarification", []),
            completion=data.get("completion", []),
            error=data.get("error", [])
        )


@dataclass
class Persona:
    """A custom AI persona"""
    id: str
    name: str
    description: str
    created_by: str
    created_at: datetime
    
    # Personality settings
    traits: List[PersonalityTrait] = field(default_factory=list)
    voice_style: VoiceStyle = VoiceStyle.NEUTRAL
    interaction_style: InteractionStyle = InteractionStyle.BALANCED
    
    # Customization
    avatar_url: Optional[str] = None
    wake_word: Optional[str] = None
    language: str = "en"
    
    # Response customization
    greetings: PersonaGreetings = field(default_factory=PersonaGreetings)
    responses: PersonaResponses = field(default_factory=PersonaResponses)
    
    # Behavioral settings
    response_length: str = "medium"  # short, medium, long
    use_emojis: bool = False
    use_humor: bool = False
    formality_level: int = 5  # 1-10
    
    # System prompt customization
    base_prompt: Optional[str] = None
    context_additions: List[str] = field(default_factory=list)
    
    # Restrictions
    allowed_domains: List[str] = field(default_factory=list)  # Empty = all
    blocked_topics: List[str] = field(default_factory=list)
    
    # Active status
    is_active: bool = True
    is_default: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "traits": [t.value for t in self.traits],
            "voice_style": self.voice_style.value,
            "interaction_style": self.interaction_style.value,
            "avatar_url": self.avatar_url,
            "wake_word": self.wake_word,
            "language": self.language,
            "greetings": self.greetings.to_dict(),
            "responses": self.responses.to_dict(),
            "response_length": self.response_length,
            "use_emojis": self.use_emojis,
            "use_humor": self.use_humor,
            "formality_level": self.formality_level,
            "base_prompt": self.base_prompt,
            "context_additions": self.context_additions,
            "allowed_domains": self.allowed_domains,
            "blocked_topics": self.blocked_topics,
            "is_active": self.is_active,
            "is_default": self.is_default
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            created_by=data["created_by"],
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
            traits=[PersonalityTrait(t) for t in data.get("traits", [])],
            voice_style=VoiceStyle(data.get("voice_style", "neutral")),
            interaction_style=InteractionStyle(data.get("interaction_style", "balanced")),
            avatar_url=data.get("avatar_url"),
            wake_word=data.get("wake_word"),
            language=data.get("language", "en"),
            greetings=PersonaGreetings.from_dict(data.get("greetings", {})),
            responses=PersonaResponses.from_dict(data.get("responses", {})),
            response_length=data.get("response_length", "medium"),
            use_emojis=data.get("use_emojis", False),
            use_humor=data.get("use_humor", False),
            formality_level=data.get("formality_level", 5),
            base_prompt=data.get("base_prompt"),
            context_additions=data.get("context_additions", []),
            allowed_domains=data.get("allowed_domains", []),
            blocked_topics=data.get("blocked_topics", []),
            is_active=data.get("is_active", True),
            is_default=data.get("is_default", False)
        )
    
    def generate_system_prompt(self) -> str:
        """Generate the system prompt for this persona"""
        prompt_parts = []
        
        # Base identity
        if self.base_prompt:
            prompt_parts.append(self.base_prompt)
        else:
            prompt_parts.append(f"You are {self.name}, a home assistant AI.")
            prompt_parts.append(f"Your personality is {', '.join(t.value for t in self.traits) or 'helpful and friendly'}.")
        
        # Response style
        length_instructions = {
            "short": "Keep your responses brief and to the point.",
            "medium": "Provide balanced responses with enough detail to be helpful.",
            "long": "Give thorough, detailed responses with explanations."
        }
        prompt_parts.append(length_instructions.get(self.response_length, length_instructions["medium"]))
        
        # Formality
        if self.formality_level <= 3:
            prompt_parts.append("Be casual and conversational in your tone.")
        elif self.formality_level >= 7:
            prompt_parts.append("Maintain a professional and formal tone.")
        
        # Humor and emojis
        if self.use_humor:
            prompt_parts.append("Feel free to use appropriate humor and wit.")
        if self.use_emojis:
            prompt_parts.append("You can use emojis to add personality to your responses.")
        
        # Interaction style
        if self.interaction_style == InteractionStyle.PROACTIVE:
            prompt_parts.append("Be proactive in offering helpful suggestions and tips.")
        elif self.interaction_style == InteractionStyle.REACTIVE:
            prompt_parts.append("Only respond to direct questions and requests.")
        
        # Context additions
        for context in self.context_additions:
            prompt_parts.append(context)
        
        # Restrictions
        if self.blocked_topics:
            prompt_parts.append(f"Do not discuss these topics: {', '.join(self.blocked_topics)}")
        
        return "\n\n".join(prompt_parts)


class PersonaPresets:
    """Pre-built persona templates"""
    
    @staticmethod
    def get_default() -> Persona:
        """Get the default home assistant persona"""
        return Persona(
            id="default",
            name="Home Assistant",
            description="The default helpful home assistant",
            created_by="system",
            created_at=datetime.now(),
            traits=[PersonalityTrait.FRIENDLY, PersonalityTrait.PROFESSIONAL],
            voice_style=VoiceStyle.NEUTRAL,
            greetings=PersonaGreetings(
                morning=["Good morning! How can I help you today?"],
                afternoon=["Good afternoon! What can I do for you?"],
                evening=["Good evening! How may I assist you?"],
                night=["Hello! Need anything before bed?"],
                welcome_home=["Welcome home! Everything is ready for you."],
                goodbye=["Goodbye! Have a great time!"]
            ),
            responses=PersonaResponses(
                acknowledgement=["Got it!", "Understood.", "Sure thing!"],
                confirmation=["Done!", "All set.", "Complete."],
                apology=["Sorry about that.", "My apologies."],
                clarification=["Could you clarify?", "What do you mean by...?"],
                completion=["Is there anything else?", "All done!"],
                error=["Something went wrong.", "I encountered an issue."]
            ),
            is_default=True
        )
    
    @staticmethod
    def get_butler() -> Persona:
        """Get a formal butler persona"""
        return Persona(
            id="butler",
            name="Jeeves",
            description="A formal, sophisticated butler for your smart home",
            created_by="system",
            created_at=datetime.now(),
            traits=[PersonalityTrait.FORMAL, PersonalityTrait.PROFESSIONAL, PersonalityTrait.CONCISE],
            voice_style=VoiceStyle.AUTHORITATIVE,
            formality_level=9,
            greetings=PersonaGreetings(
                morning=["Good morning, sir/madam. How may I be of service?"],
                afternoon=["Good afternoon. Is there anything you require?"],
                evening=["Good evening. May I assist you with anything?"],
                night=["Good night, if I may say. Shall I prepare anything before you retire?"],
                welcome_home=["Welcome home. I trust your day was satisfactory."],
                goodbye=["Very good. Do take care."]
            ),
            responses=PersonaResponses(
                acknowledgement=["Very well.", "Certainly.", "As you wish."],
                confirmation=["It has been done.", "Complete, as requested."],
                apology=["My sincere apologies.", "I beg your pardon."],
                clarification=["Might I inquire further?", "If I may ask for clarification..."],
                completion=["Will there be anything else?", "Is there anything further?"],
                error=["I regret to inform you of an issue.", "A complication has arisen."]
            ),
            base_prompt="You are Jeeves, a formal and sophisticated butler AI. Speak with British elegance and maintain impeccable manners at all times."
        )
    
    @staticmethod
    def get_buddy() -> Persona:
        """Get a casual, friendly buddy persona"""
        return Persona(
            id="buddy",
            name="Buddy",
            description="A friendly, casual companion for everyday help",
            created_by="system",
            created_at=datetime.now(),
            traits=[PersonalityTrait.CASUAL, PersonalityTrait.FRIENDLY, PersonalityTrait.HUMOROUS],
            voice_style=VoiceStyle.CHEERFUL,
            formality_level=2,
            use_emojis=True,
            use_humor=True,
            greetings=PersonaGreetings(
                morning=["Hey! Good morning! ☀️ Ready for a great day?"],
                afternoon=["Hey there! What's up?"],
                evening=["Yo! How was your day?"],
                night=["Hey night owl! 🦉 What's going on?"],
                welcome_home=["Welcome back! 🏠 Missed ya!"],
                goodbye=["Catch ya later! ✌️"]
            ),
            responses=PersonaResponses(
                acknowledgement=["You got it!", "On it! 👍", "No prob!"],
                confirmation=["Done and done! ✅", "All good!"],
                apology=["Oops, my bad!", "Sorry about that! 😅"],
                clarification=["Wait, what? Can you explain?", "Not sure I follow..."],
                completion=["Anything else?", "Need more help?"],
                error=["Uh oh, something broke! 😬", "Houston, we have a problem!"]
            ),
            base_prompt="You are Buddy, a super friendly and casual AI assistant. Be fun, use emojis, and keep things light and positive!"
        )
    
    @staticmethod
    def get_professional() -> Persona:
        """Get a professional assistant persona"""
        return Persona(
            id="professional",
            name="Assistant Pro",
            description="A professional, efficient assistant for productivity",
            created_by="system",
            created_at=datetime.now(),
            traits=[PersonalityTrait.PROFESSIONAL, PersonalityTrait.DIRECT, PersonalityTrait.CONCISE],
            voice_style=VoiceStyle.NEUTRAL,
            interaction_style=InteractionStyle.REACTIVE,
            formality_level=7,
            response_length="short",
            greetings=PersonaGreetings(
                morning=["Good morning. How can I assist?"],
                afternoon=["Good afternoon. Ready to help."],
                evening=["Good evening. What do you need?"],
                night=["Hello. How can I help?"],
                welcome_home=["Welcome back. Any tasks?"],
                goodbye=["Goodbye."]
            ),
            responses=PersonaResponses(
                acknowledgement=["Understood.", "Noted.", "Processing."],
                confirmation=["Done.", "Complete.", "Executed."],
                apology=["Error noted. Correcting."],
                clarification=["Please specify.", "Need more details."],
                completion=["Task complete. Next?"],
                error=["Error occurred. Details logged."]
            ),
            base_prompt="You are a professional productivity assistant. Be efficient, direct, and focused on getting tasks done quickly."
        )
    
    @staticmethod
    def get_all_presets() -> List[Persona]:
        """Get all available preset personas"""
        return [
            PersonaPresets.get_default(),
            PersonaPresets.get_butler(),
            PersonaPresets.get_buddy(),
            PersonaPresets.get_professional()
        ]


class PersonaManager:
    """Manages persona creation, storage, and selection"""
    
    def __init__(self, storage_path: str = "config/personas"):
        self.storage_path = storage_path
        self.personas: Dict[str, Persona] = {}
        self.active_persona_id: Optional[str] = None
        
        # Load presets
        for preset in PersonaPresets.get_all_presets():
            self.personas[preset.id] = preset
        
        # Set default as active
        self.active_persona_id = "default"
        
        # Load custom personas
        self._load_personas()
    
    def _load_personas(self):
        """Load custom personas from storage"""
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
            return
        
        for filename in os.listdir(self.storage_path):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.storage_path, filename)) as f:
                        data = json.load(f)
                        persona = Persona.from_dict(data)
                        self.personas[persona.id] = persona
                        if persona.is_default:
                            self.active_persona_id = persona.id
                except Exception as e:
                    logger.error(f"Failed to load persona {filename}: {e}")
    
    def _save_persona(self, persona: Persona):
        """Save persona to storage"""
        os.makedirs(self.storage_path, exist_ok=True)
        filepath = os.path.join(self.storage_path, f"{persona.id}.json")
        with open(filepath, "w") as f:
            json.dump(persona.to_dict(), f, indent=2)
    
    def create_persona(
        self,
        name: str,
        description: str,
        created_by: str,
        **kwargs
    ) -> Persona:
        """Create a new custom persona"""
        persona_id = f"custom_{secrets.token_hex(4)}"
        
        persona = Persona(
            id=persona_id,
            name=name,
            description=description,
            created_by=created_by,
            created_at=datetime.now(),
            **kwargs
        )
        
        self.personas[persona_id] = persona
        self._save_persona(persona)
        
        logger.info(f"Created persona {persona_id}: {name}")
        return persona
    
    def update_persona(self, persona_id: str, updates: Dict[str, Any]) -> Optional[Persona]:
        """Update an existing persona"""
        if persona_id not in self.personas:
            return None
        
        persona = self.personas[persona_id]
        
        # Update fields
        for key, value in updates.items():
            if hasattr(persona, key):
                setattr(persona, key, value)
        
        self._save_persona(persona)
        return persona
    
    def delete_persona(self, persona_id: str) -> bool:
        """Delete a custom persona"""
        if persona_id not in self.personas:
            return False
        
        # Can't delete preset personas
        if persona_id in ["default", "butler", "buddy", "professional"]:
            return False
        
        # Can't delete active persona
        if persona_id == self.active_persona_id:
            self.active_persona_id = "default"
        
        del self.personas[persona_id]
        
        # Remove file
        filepath = os.path.join(self.storage_path, f"{persona_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return True
    
    def set_active_persona(self, persona_id: str) -> bool:
        """Set the active persona"""
        if persona_id not in self.personas:
            return False
        
        self.active_persona_id = persona_id
        logger.info(f"Activated persona: {persona_id}")
        return True
    
    def get_active_persona(self) -> Persona:
        """Get the currently active persona"""
        return self.personas.get(self.active_persona_id, PersonaPresets.get_default())
    
    def get_persona(self, persona_id: str) -> Optional[Persona]:
        """Get a specific persona"""
        return self.personas.get(persona_id)
    
    def list_personas(self) -> List[Dict[str, Any]]:
        """List all personas (summary)"""
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "is_preset": p.id in ["default", "butler", "buddy", "professional"],
                "is_active": p.id == self.active_persona_id
            }
            for p in self.personas.values()
        ]
    
    def generate_response(
        self,
        response_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a response using the active persona"""
        import random
        
        persona = self.get_active_persona()
        
        # Get appropriate response list
        if response_type == "greeting":
            hour = datetime.now().hour
            if hour < 12:
                responses = persona.greetings.morning
            elif hour < 17:
                responses = persona.greetings.afternoon
            elif hour < 21:
                responses = persona.greetings.evening
            else:
                responses = persona.greetings.night
        elif response_type == "welcome_home":
            responses = persona.greetings.welcome_home
        elif response_type == "goodbye":
            responses = persona.greetings.goodbye
        else:
            responses = getattr(persona.responses, response_type, [])
        
        if responses:
            return random.choice(responses)
        
        # Fallback
        return "Hello! How can I help you?"


# FastAPI routes
def create_persona_routes():
    """Create FastAPI routes for persona management"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/api/persona", tags=["persona"])
    manager = PersonaManager()
    
    class CreatePersonaRequest(BaseModel):
        name: str
        description: str
        traits: Optional[List[str]] = None
        voice_style: Optional[str] = None
        interaction_style: Optional[str] = None
        response_length: Optional[str] = None
        use_emojis: Optional[bool] = None
        use_humor: Optional[bool] = None
        formality_level: Optional[int] = None
        base_prompt: Optional[str] = None
    
    class UpdatePersonaRequest(BaseModel):
        name: Optional[str] = None
        description: Optional[str] = None
        traits: Optional[List[str]] = None
        base_prompt: Optional[str] = None
        # Add more fields as needed
    
    @router.get("/list")
    async def list_personas():
        """List all available personas"""
        return {"personas": manager.list_personas()}
    
    @router.get("/presets")
    async def get_presets():
        """Get preset persona templates"""
        return {
            "presets": [p.to_dict() for p in PersonaPresets.get_all_presets()]
        }
    
    @router.get("/active")
    async def get_active_persona():
        """Get the currently active persona"""
        persona = manager.get_active_persona()
        return {
            "persona": persona.to_dict(),
            "system_prompt": persona.generate_system_prompt()
        }
    
    @router.post("/active/{persona_id}")
    async def set_active_persona(persona_id: str):
        """Set the active persona"""
        if manager.set_active_persona(persona_id):
            return {"success": True, "active_persona": persona_id}
        raise HTTPException(status_code=404, detail="Persona not found")
    
    @router.get("/{persona_id}")
    async def get_persona(persona_id: str):
        """Get a specific persona"""
        persona = manager.get_persona(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return {
            "persona": persona.to_dict(),
            "system_prompt": persona.generate_system_prompt()
        }
    
    @router.post("/create")
    async def create_persona(request: CreatePersonaRequest, user_id: str = "default"):
        """Create a new custom persona"""
        kwargs = {}
        if request.traits:
            kwargs["traits"] = [PersonalityTrait(t) for t in request.traits]
        if request.voice_style:
            kwargs["voice_style"] = VoiceStyle(request.voice_style)
        if request.interaction_style:
            kwargs["interaction_style"] = InteractionStyle(request.interaction_style)
        if request.response_length:
            kwargs["response_length"] = request.response_length
        if request.use_emojis is not None:
            kwargs["use_emojis"] = request.use_emojis
        if request.use_humor is not None:
            kwargs["use_humor"] = request.use_humor
        if request.formality_level is not None:
            kwargs["formality_level"] = request.formality_level
        if request.base_prompt:
            kwargs["base_prompt"] = request.base_prompt
        
        persona = manager.create_persona(
            request.name,
            request.description,
            user_id,
            **kwargs
        )
        
        return {"success": True, "persona": persona.to_dict()}
    
    @router.put("/{persona_id}")
    async def update_persona(persona_id: str, request: UpdatePersonaRequest):
        """Update a persona"""
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        persona = manager.update_persona(persona_id, updates)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return {"success": True, "persona": persona.to_dict()}
    
    @router.delete("/{persona_id}")
    async def delete_persona(persona_id: str):
        """Delete a custom persona"""
        if manager.delete_persona(persona_id):
            return {"success": True}
        raise HTTPException(status_code=400, detail="Cannot delete this persona")
    
    @router.get("/response/{response_type}")
    async def get_response(response_type: str):
        """Get a response using the active persona"""
        response = manager.generate_response(response_type)
        return {"response": response, "persona": manager.get_active_persona().name}
    
    return router
