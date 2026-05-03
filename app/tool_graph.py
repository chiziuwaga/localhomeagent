"""
Local Model Tool Call Graph (F4.6.7)
Implements a directed acyclic graph for tool calling with local LLMs
Based on LangGraph patterns but optimized for local execution
"""

import json
import asyncio
from typing import Dict, Any, List, Optional, Callable, TypedDict
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolState(TypedDict):
    """State passed between tool nodes"""
    messages: List[Dict[str, str]]
    current_tool: Optional[str]
    tool_results: Dict[str, Any]
    next_action: Optional[str]
    energy_used: float
    context: Dict[str, Any]


# Import LLM client (moved down to avoid circular imports if any, though standard imports are better)
from .llm_client import get_llm_client, LLMResponse


class NodeType(Enum):
    """Types of nodes in the tool graph"""
    START = "start"
    TOOL = "tool"
    LLM = "llm"
    CONDITION = "condition"
    END = "end"


@dataclass
class ToolNode:
    """Represents a node in the tool call graph"""
    name: str
    node_type: NodeType
    handler: Callable
    energy_cost: float = 1.0
    description: str = ""
    required_params: List[str] = field(default_factory=list)
    edges: Dict[str, 'ToolNode'] = field(default_factory=dict)
    
    async def execute(self, state: ToolState) -> ToolState:
        """Execute this node's handler"""
        state['energy_used'] += self.energy_cost
        result = await self.handler(state)
        return result


class LocalToolGraph:
    """
    Manages tool calling flow for local LLM agents
    Implements energy-aware routing and fallback chains
    """
    
    def __init__(self, max_energy: float = 100.0):
        self.nodes: Dict[str, ToolNode] = {}
        self.start_node: Optional[ToolNode] = None
        self.max_energy = max_energy
        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        self._setup_base_tools()
    
    def _setup_base_tools(self):
        """Register base tools available to all agents"""
        self.register_tool(
            "search_knowledge",
            self._search_knowledge_tool,
            description="Search local knowledge base",
            energy_cost=2.0
        )
        
        self.register_tool(
            "check_device_state", 
            self._check_device_state_tool,
            description="Check smart home device state",
            energy_cost=1.0
        )
        
        self.register_tool(
            "control_device",
            self._control_device_tool,
            description="Control smart home device",
            energy_cost=5.0,
            required_params=["device_id", "action"]
        )
        
        self.register_tool(
            "get_weather",
            self._get_weather_tool,
            description="Get current weather",
            energy_cost=3.0
        )
        
        self.register_tool(
            "set_reminder",
            self._set_reminder_tool,
            description="Set a reminder",
            energy_cost=2.0,
            required_params=["time", "message"]
        )
        
        self.register_tool(
            "get_calendar",
            self._get_calendar_tool,
            description="Get calendar events",
            energy_cost=2.0
        )
        
        self.register_tool(
            "send_notification",
            self._send_notification_tool,
            description="Send a notification to user",
            energy_cost=1.0,
            required_params=["message"]
        )
    
    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        energy_cost: float = 1.0,
        required_params: Optional[List[str]] = None
    ):
        """Register a tool that can be called by the LLM"""
        self.tools_registry[name] = {
            'handler': handler,
            'description': description,
            'energy_cost': energy_cost,
            'required_params': required_params or []
        }
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible tool schema for LLM"""
        tools = []
        for name, tool in self.tools_registry.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool['description'],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            param: {"type": "string", "description": f"The {param} parameter"}
                            for param in tool['required_params']
                        },
                        "required": tool['required_params']
                    }
                }
            })
        return tools
    
    def add_node(self, node: ToolNode) -> 'LocalToolGraph':
        """Add a node to the graph"""
        self.nodes[node.name] = node
        if node.node_type == NodeType.START:
            self.start_node = node
        return self
    
    def add_edge(self, from_node: str, to_node: str, condition: Optional[Callable] = None):
        """Add an edge between nodes"""
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError(f"Nodes must exist before adding edge: {from_node} -> {to_node}")
        
        self.nodes[from_node].edges[to_node] = self.nodes[to_node]
        return self
    
    def add_conditional_edge(self, from_node: str, condition: Callable[[ToolState], str]):
        """Add a conditional edge that routes based on state"""
        if from_node not in self.nodes:
            raise ValueError(f"Node must exist: {from_node}")
        
        # Store condition in node for later evaluation
        self.nodes[from_node].condition = condition
        return self
    
    def build_tool_calling_graph(self) -> 'LocalToolGraph':
        """Build the standard tool calling flow graph"""
        
        # Start node - analyze user intent
        start = ToolNode(
            name="analyze_intent",
            node_type=NodeType.START,
            handler=self._analyze_intent,
            energy_cost=1.0,
            description="Analyze user intent to determine tool needs"
        )
        
        # Tool selection node
        select_tool = ToolNode(
            name="select_tool",
            node_type=NodeType.LLM,
            handler=self._select_tool,
            energy_cost=2.0,
            description="Select appropriate tool based on intent"
        )
        
        # Tool execution node
        execute_tool = ToolNode(
            name="execute_tool",
            node_type=NodeType.TOOL,
            handler=self._execute_tool,
            energy_cost=0.0,  # Cost added by specific tool
            description="Execute selected tool"
        )
        
        # Check if more tools needed
        check_more = ToolNode(
            name="check_more_tools",
            node_type=NodeType.CONDITION,
            handler=self._check_more_tools,
            energy_cost=0.5,
            description="Check if more tools are needed"
        )
        
        # Response generation node
        generate_response = ToolNode(
            name="generate_response",
            node_type=NodeType.LLM,
            handler=self._generate_response,
            energy_cost=3.0,
            description="Generate final response with tool results"
        )
        
        # End node
        end = ToolNode(
            name="end",
            node_type=NodeType.END,
            handler=self._end_handler,
            energy_cost=0.0,
            description="Finalize and return results"
        )
        
        # Add nodes
        self.add_node(start)
        self.add_node(select_tool)
        self.add_node(execute_tool)
        self.add_node(check_more)
        self.add_node(generate_response)
        self.add_node(end)
        
        # Add edges (flow)
        self.add_edge("analyze_intent", "select_tool")
        self.add_edge("select_tool", "execute_tool")
        self.add_edge("execute_tool", "check_more_tools")
        self.add_edge("check_more_tools", "select_tool")  # Loop back if more tools needed
        self.add_edge("check_more_tools", "generate_response")  # Continue to response
        self.add_edge("generate_response", "end")
        
        return self
    
    async def _analyze_intent(self, state: ToolState) -> ToolState:
        """Analyze user intent from messages"""
        last_message = state['messages'][-1]['content'] if state['messages'] else ""
        
        # Intent detection keywords
        intent_keywords = {
            'device_control': ['turn', 'switch', 'control', 'set', 'dim', 'adjust', 'lock', 'unlock'],
            'device_query': ['check', 'status', 'state', 'is', 'what', 'how', 'show'],
            'weather': ['weather', 'temperature', 'forecast', 'rain', 'sunny', 'cold', 'hot'],
            'reminder': ['remind', 'reminder', 'alert', 'schedule', 'timer'],
            'calendar': ['calendar', 'meeting', 'appointment', 'event', 'schedule'],
            'notification': ['notify', 'send', 'message', 'tell']
        }
        
        intents = []
        lower_message = last_message.lower()
        
        for intent, keywords in intent_keywords.items():
            if any(word in lower_message for word in keywords):
                intents.append(intent)
        
        state['context']['intents'] = intents
        state['context']['pending_intents'] = intents.copy()
        return state
    
    async def _select_tool(self, state: ToolState) -> ToolState:
        """Select the appropriate tool based on intent using LLM"""
        last_message = state['messages'][-1]['content'] if state['messages'] else ""
        
        # Get available tools
        tools_schema = self.get_tools_schema()
        
        # Construct prompt for tool selection
        system_prompt = f"""You are an AI home assistant. Select the best tool to handle the user's request.
Available tools:
{json.dumps(tools_schema, indent=2)}

Reply with a JSON object containing:
{{
    "tool": "tool_name_or_null",
    "reasoning": "why you chose this tool"
}}
If no tool is needed (just conversation), set "tool" to null.
"""

        try:
            client = get_llm_client()
            response = await client.generate(
                prompt=f"User request: {last_message}",
                system_prompt=system_prompt,
                temperature=0.1 # Low temperature for reliable tool selection
            )
            
            try:
                # Clean response (remove markdown code blocks if present)
                content = response.content.replace("```json", "").replace("```", "").strip()
                selection = json.loads(content)
                tool_name = selection.get("tool")
                
                if tool_name and tool_name in self.tools_registry:
                    state['current_tool'] = tool_name
                    logger.info(f"LLM selected tool: {tool_name}")
                else:
                    state['current_tool'] = None
                    
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM tool selection: {response.content}")
                # Fallback to heuristic
                return await self._select_tool_heuristic(state)
                
        except Exception as e:
            logger.error(f"LLM tool selection failed: {e}")
            # Fallback to heuristic
            return await self._select_tool_heuristic(state)

        return state

    async def _select_tool_heuristic(self, state: ToolState) -> ToolState:
        """Fallback heuristic tool selection"""
        pending = state['context'].get('pending_intents', [])
        
        if not pending:
            state['current_tool'] = "search_knowledge" # Default fallback
            return state
        
        # Get next pending intent
        intent = pending.pop(0)
        state['context']['pending_intents'] = pending
        
        # Map intents to tools
        tool_map = {
            'device_control': 'control_device',
            'device_query': 'check_device_state',
            'weather': 'get_weather',
            'reminder': 'set_reminder',
            'calendar': 'get_calendar',
            'notification': 'send_notification'
        }
        
        state['current_tool'] = tool_map.get(intent, 'search_knowledge')
        return state
    
    async def _execute_tool(self, state: ToolState) -> ToolState:
        """Execute the selected tool"""
        tool_name = state['current_tool']
        
        if not tool_name:
            return state
        
        if tool_name in self.tools_registry:
            tool = self.tools_registry[tool_name]
            
            # Check energy budget
            if state['energy_used'] + tool['energy_cost'] > self.max_energy:
                state['tool_results'][tool_name] = {
                    'error': 'Insufficient energy budget for tool execution'
                }
                return state
            
            # Execute tool
            try:
                result = await tool['handler'](state)
                state['tool_results'][tool_name] = result
                state['energy_used'] += tool['energy_cost']
                logger.info(f"Tool {tool_name} executed successfully")
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                state['tool_results'][tool_name] = {'error': str(e)}
        
        return state
    
    async def _check_more_tools(self, state: ToolState) -> ToolState:
        """Check if more tools are needed"""
        pending = state['context'].get('pending_intents', [])
        state['next_action'] = 'select_tool' if pending else 'generate_response'
        return state
    
    async def _generate_response(self, state: ToolState) -> ToolState:
        """Generate response incorporating tool results using LLM"""
        tool_results = state.get('tool_results', {})
        last_user_message = state['messages'][0]['content'] # Assuming first is user for single turn
        
        # Construct context from tool results
        results_context = "Tool Results:\n"
        for tool, result in tool_results.items():
            results_context += f"- {tool}: {json.dumps(result)}\n"
            
        system_prompt = f"""You are a helpful home assistant. 
Use the following tool results to answer the user's request.
If the tool failed or simulated execution, explain that clearly.
Be concise and friendly.

{results_context}
"""

        try:
            client = get_llm_client()
            response = await client.generate(
                prompt=last_user_message,
                system_prompt=system_prompt,
                temperature=0.7 
            )
            
            final_response = response.content
            
        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")
            final_response = "I processed your request, but had trouble generating a response."

        state['messages'].append({
            'role': 'assistant',
            'content': final_response
        })
        
        return state
    
    async def _end_handler(self, state: ToolState) -> ToolState:
        """Finalize the tool calling flow"""
        logger.info(f"Tool graph completed. Energy used: {state['energy_used']}")
        return state
    
    # Tool implementations
    async def _search_knowledge_tool(self, state: ToolState) -> Dict[str, Any]:
        """
        Search local knowledge base using RAG (Retrieval Augmented Generation)
        Uses simple TF-IDF for now, can be upgraded to vector embeddings
        """
        query = state['messages'][-1]['content'] if state['messages'] else ""
        
        # Knowledge base location
        kb_path = Path("config/knowledge_base")
        if not kb_path.exists():
            kb_path.mkdir(parents=True, exist_ok=True)
            # Create sample knowledge file
            sample_path = kb_path / "property_rules.md"
            sample_path.write_text("""# Property Rules
            
## Quiet Hours
- Weekdays: 10 PM - 7 AM
- Weekends: 11 PM - 8 AM

## Common Areas
- Kitchen: Clean after use
- Laundry: No reservations after 9 PM
- Living Room: Available for all residents

## Guest Policy
- Guests must register at reception
- Maximum 2 guests per resident
- Overnight guests require 24hr notice
""")
        
        try:
            # Simple keyword search across all knowledge files
            results = []
            query_terms = query.lower().split()
            
            for doc_path in kb_path.glob("**/*.md"):
                content = doc_path.read_text()
                content_lower = content.lower()
                
                # Score based on term frequency
                score = sum(content_lower.count(term) for term in query_terms)
                
                if score > 0:
                    # Extract relevant snippet
                    for term in query_terms:
                        idx = content_lower.find(term)
                        if idx >= 0:
                            start = max(0, idx - 100)
                            end = min(len(content), idx + 200)
                            snippet = content[start:end].strip()
                            results.append({
                                "source": doc_path.name,
                                "score": score,
                                "snippet": f"...{snippet}..."
                            })
                            break
            
            # Sort by score
            results.sort(key=lambda x: x["score"], reverse=True)
            
            if results:
                return {
                    "results": results[:3],  # Top 3 matches
                    "count": len(results),
                    "query": query
                }
            else:
                return {
                    "results": [],
                    "count": 0,
                    "message": f"No knowledge base entries found for: {query[:50]}"
                }
                
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return {"error": str(e), "results": []}
    
    async def _check_device_state_tool(self, state: ToolState) -> Dict[str, Any]:
        """Check device state - integrates with home_assistant.py"""
        try:
            from .home_assistant import HomeAssistantClient
            ha = HomeAssistantClient()
            devices = await ha.discover_devices()
            return {'devices': devices[:5]}  # Return first 5 devices
        except Exception as e:
            return {'devices': [{'name': 'Living Room Light', 'state': 'on'}], 'simulated': True}
    
    async def _control_device_tool(self, state: ToolState) -> Dict[str, Any]:
        """Control a device - integrates with home_assistant.py"""
        # Extract device and action from context
        message = state['messages'][-1]['content'].lower() if state['messages'] else ""
        
        action = "turn_on" if "on" in message else "turn_off" if "off" in message else "toggle"
        
        try:
            from .home_assistant import HomeAssistantClient
            ha = HomeAssistantClient()
            result = await ha.control_device("light.living_room", action)
            return {'status': 'Device controlled successfully', 'action': action}
        except Exception as e:
            return {'status': f'Device {action} simulated', 'simulated': True}
    
    async def _get_weather_tool(self, state: ToolState) -> Dict[str, Any]:
        """Get weather information from external API"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # Free weather API
                async with session.get(
                    "https://wttr.in/?format=j1",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data.get('current_condition', [{}])[0]
                        return {
                            'weather': current.get('weatherDesc', [{}])[0].get('value', 'Unknown'),
                            'temperature': f"{current.get('temp_F', 'N/A')}°F",
                            'humidity': f"{current.get('humidity', 'N/A')}%"
                        }
        except Exception as e:
            logger.warning(f"Weather API failed: {e}")
        
        return {'weather': 'Sunny, 72°F', 'simulated': True}
    
    async def _set_reminder_tool(self, state: ToolState) -> Dict[str, Any]:
        """Set a reminder - saves to local storage"""
        message = state['messages'][-1]['content'] if state['messages'] else ""
        
        # Simple time extraction
        import re
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', message.lower())
        reminder_time = time_match.group(1) if time_match else "soon"
        
        # Save reminder to file
        reminders_file = Path("config/reminders.json")
        reminders_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            existing = json.loads(reminders_file.read_text()) if reminders_file.exists() else []
        except Exception:
            existing = []
        
        existing.append({
            'time': reminder_time,
            'message': message,
            'created': asyncio.get_event_loop().time()
        })
        
        reminders_file.write_text(json.dumps(existing, indent=2))
        
        return {'reminder': f'Reminder set for {reminder_time}', 'saved': True}
    
    async def _get_calendar_tool(self, state: ToolState) -> Dict[str, Any]:
        """
        Get calendar events - supports local JSON calendar and CalDAV
        
        For Google Calendar:
        1. Set up OAuth credentials in config/google_calendar.json
        2. Run the setup wizard at /settings to authorize
        3. Events will sync automatically
        
        Falls back to local JSON calendar for offline operation
        """
        from datetime import datetime, timedelta
        
        # Check for Google Calendar config
        google_config_path = Path("config/google_calendar.json")
        caldav_config_path = Path("config/caldav.json")
        local_calendar_path = Path("config/calendar_events.json")
        
        events = []
        source = "local"
        
        # Try Google Calendar first
        if google_config_path.exists():
            try:
                google_config = json.loads(google_config_path.read_text())
                if google_config.get("access_token"):
                    events = await self._fetch_google_calendar_events(google_config)
                    source = "google"
            except Exception as e:
                logger.warning(f"Google Calendar fetch failed: {e}")
        
        # Try CalDAV (Nextcloud, iCloud, etc.)
        if not events and caldav_config_path.exists():
            try:
                caldav_config = json.loads(caldav_config_path.read_text())
                events = await self._fetch_caldav_events(caldav_config)
                source = "caldav"
            except Exception as e:
                logger.warning(f"CalDAV fetch failed: {e}")
        
        # Fall back to local calendar
        if not events:
            local_calendar_path.parent.mkdir(parents=True, exist_ok=True)
            
            if local_calendar_path.exists():
                try:
                    events = json.loads(local_calendar_path.read_text())
                except Exception:
                    events = []
            
            # Generate sample events if empty
            if not events:
                today = datetime.now()
                events = [
                    {
                        "id": "sample_1",
                        "title": "House Meeting",
                        "time": (today.replace(hour=10, minute=0)).isoformat(),
                        "description": "Monthly resident meeting"
                    },
                    {
                        "id": "sample_2",
                        "title": "Maintenance Window",
                        "time": (today + timedelta(days=1)).replace(hour=14, minute=0).isoformat(),
                        "description": "HVAC inspection"
                    }
                ]
                local_calendar_path.write_text(json.dumps(events, indent=2))
        
        # Filter to upcoming events (next 7 days)
        now = datetime.now()
        upcoming = []
        for event in events[:10]:  # Limit to 10 events
            try:
                event_time = datetime.fromisoformat(event.get("time", ""))
                if now <= event_time <= now + timedelta(days=7):
                    upcoming.append({
                        "title": event.get("title", "Untitled"),
                        "time": event_time.strftime("%I:%M %p on %b %d"),
                        "description": event.get("description", "")
                    })
            except Exception:
                # Include if time parsing fails
                upcoming.append({
                    "title": event.get("title", "Untitled"),
                    "time": event.get("time", "Unknown"),
                    "description": event.get("description", "")
                })
        
        return {
            "events": upcoming or [{"title": "No upcoming events", "time": ""}],
            "source": source,
            "count": len(upcoming)
        }
    
    async def _fetch_google_calendar_events(self, config: dict) -> List[dict]:
        """Fetch events from Google Calendar API"""
        import aiohttp
        from datetime import datetime, timezone
        
        access_token = config.get("access_token")
        if not access_token:
            return []
        
        # Google Calendar API endpoint
        calendar_id = config.get("calendar_id", "primary")
        time_min = datetime.now(timezone.utc).isoformat()
        time_max = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        
        url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
            f"?timeMin={time_min}&timeMax={time_max}&singleEvents=true&orderBy=startTime"
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [
                        {
                            "id": item.get("id"),
                            "title": item.get("summary", "Untitled"),
                            "time": item.get("start", {}).get("dateTime", item.get("start", {}).get("date", "")),
                            "description": item.get("description", "")
                        }
                        for item in data.get("items", [])
                    ]
                elif resp.status == 401:
                    # Token expired - would need refresh
                    logger.warning("Google Calendar token expired")
        
        return []
    
    async def _fetch_caldav_events(self, config: dict) -> List[dict]:
        """Fetch events from CalDAV server (Nextcloud, iCloud, etc.)"""
        import aiohttp
        from datetime import datetime
        
        server_url = config.get("url")
        username = config.get("username")
        password = config.get("password")
        
        if not all([server_url, username, password]):
            return []
        
        # Basic CalDAV REPORT request for events
        caldav_query = """<?xml version="1.0" encoding="utf-8" ?>
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
                <D:getetag/>
                <C:calendar-data/>
            </D:prop>
            <C:filter>
                <C:comp-filter name="VCALENDAR">
                    <C:comp-filter name="VEVENT"/>
                </C:comp-filter>
            </C:filter>
        </C:calendar-query>"""
        
        try:
            auth = aiohttp.BasicAuth(username, password)
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.request(
                    "REPORT",
                    server_url,
                    data=caldav_query,
                    headers={"Content-Type": "application/xml", "Depth": "1"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status in [200, 207]:
                        # Parse iCal data - simplified for demo
                        # In production, use icalendar library
                        logger.info("CalDAV events fetched successfully")
                        return []  # Would parse iCal here
        except Exception as e:
            logger.error(f"CalDAV fetch error: {e}")
        
        return []
    
    async def _send_notification_tool(self, state: ToolState) -> Dict[str, Any]:
        """Send a notification to user"""
        message = state['messages'][-1]['content'] if state['messages'] else "Notification"
        
        # Log notification
        logger.info(f"NOTIFICATION: {message}")
        
        # Could integrate with system notifications, push notifications, etc.
        return {'sent': True, 'message': message[:100]}
    
    async def execute(self, initial_state: Optional[ToolState] = None) -> ToolState:
        """Execute the graph from start to end"""
        if not self.start_node:
            raise ValueError("No start node defined in graph")
        
        state: ToolState = initial_state or {
            'messages': [],
            'current_tool': None,
            'tool_results': {},
            'next_action': None,
            'energy_used': 0.0,
            'context': {}
        }
        
        current_node = self.start_node
        visited_count: Dict[str, int] = {}
        max_visits = 10  # Prevent infinite loops
        
        while current_node and current_node.node_type != NodeType.END:
            node_name = current_node.name
            visited_count[node_name] = visited_count.get(node_name, 0) + 1
            
            if visited_count[node_name] > max_visits:
                logger.warning(f"Max visits reached for node: {node_name}")
                break
            
            # Execute current node
            state = await current_node.execute(state)
            
            # Check energy budget
            if state['energy_used'] >= self.max_energy:
                logger.warning(f"Energy budget exhausted: {state['energy_used']}/{self.max_energy}")
                break
            
            # Determine next node
            if current_node.node_type == NodeType.CONDITION:
                # Use next_action from state to determine path
                next_action = state.get('next_action')
                if next_action and next_action in current_node.edges:
                    current_node = current_node.edges[next_action]
                elif current_node.edges:
                    # Default to first edge if no match
                    current_node = list(current_node.edges.values())[0]
                else:
                    break
            elif current_node.edges:
                # Take first edge for non-conditional nodes
                current_node = list(current_node.edges.values())[0]
            else:
                break
        
        # Execute end node if we reached it
        if current_node and current_node.node_type == NodeType.END:
            state = await current_node.execute(state)
        
        return state
    
    async def process_message(self, user_message: str) -> str:
        """Convenience method to process a single user message"""
        initial_state: ToolState = {
            'messages': [{'role': 'user', 'content': user_message}],
            'current_tool': None,
            'tool_results': {},
            'next_action': None,
            'energy_used': 0.0,
            'context': {}
        }
        
        final_state = await self.execute(initial_state)
        
        # Get last assistant message
        for msg in reversed(final_state['messages']):
            if msg['role'] == 'assistant':
                return msg['content']
        
        return "I processed your request."


# LLM Runtime Configuration (F4.6.7)
class LLMRuntimeConfig:
    """Configuration for local LLM runtime options"""
    
    SUPPORTED_RUNTIMES = {
        'llama.cpp': {
            'name': 'llama.cpp',
            'description': 'High-performance C++ inference',
            'install': 'pip install llama-cpp-python',
            'models': ['llama-3.2-1b', 'llama-3.2-3b', 'llama-3.2-8b']
        },
        'ollama': {
            'name': 'Ollama',
            'description': 'Easy-to-use local LLM server',
            'install': 'Download from ollama.ai',
            'models': ['llama3.2', 'mistral', 'phi3']
        },
        'vllm': {
            'name': 'vLLM',
            'description': 'High-throughput inference server',
            'install': 'pip install vllm',
            'models': ['meta-llama/Llama-3.2-1B', 'meta-llama/Llama-3.2-3B']
        },
        'transformers': {
            'name': 'HuggingFace Transformers',
            'description': 'Python-native inference',
            'install': 'pip install transformers torch',
            'models': ['meta-llama/Llama-3.2-1B-Instruct']
        }
    }
    
    def __init__(self, runtime: str = 'llama.cpp', model: str = 'llama-3.2-3b'):
        self.runtime = runtime
        self.model = model
        self.config_file = Path("config/llm_runtime.json")
    
    def save(self):
        """Save configuration to file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps({
            'runtime': self.runtime,
            'model': self.model
        }, indent=2))
    
    @classmethod
    def load(cls) -> 'LLMRuntimeConfig':
        """Load configuration from file"""
        config_file = Path("config/llm_runtime.json")
        if config_file.exists():
            data = json.loads(config_file.read_text())
            return cls(runtime=data.get('runtime', 'llama.cpp'), model=data.get('model', 'llama-3.2-3b'))
        return cls()
    
    def get_runtime_info(self) -> Dict[str, Any]:
        """Get information about current runtime"""
        return self.SUPPORTED_RUNTIMES.get(self.runtime, {})


# Example usage and testing
async def demo_tool_graph():
    """Demonstrate the tool calling graph"""
    graph = LocalToolGraph(max_energy=50.0)
    graph.build_tool_calling_graph()
    
    # Test messages
    test_messages = [
        "Turn on the living room light",
        "What's the weather like?",
        "Remind me to call mom at 5pm",
        "Check the status of my devices and get the weather",
    ]
    
    for msg in test_messages:
        print(f"\nUser: {msg}")
        response = await graph.process_message(msg)
        print(f"Assistant: {response}")
    
    return graph


if __name__ == "__main__":
    asyncio.run(demo_tool_graph())
