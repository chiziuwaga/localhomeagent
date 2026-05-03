# Local Home Agent - Setup & Configuration Guide

**Version:** 1.0.0 | **Last Updated:** December 9, 2025

This guide covers the complete setup of the Local Home Agent for co-living property management.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Role-Based Access Control (RBAC)](#role-based-access-control)
6. [IoT Device Integration](#iot-device-integration)
7. [AI Model Setup](#ai-model-setup)
8. [Security Best Practices](#security-best-practices)
9. [API Reference](#api-reference)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Fix-It-For-Me-AI/local-home-agent.git
cd local-home-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure settings
cp config/config.example.yaml config/config.yaml

# 4. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Access the agent at: `http://localhost:8000`

---

## System Requirements

### Minimum
- **Python:** 3.9+
- **RAM:** 4GB (for 1B parameter LLM)
- **Storage:** 5GB
- **Network:** Local WiFi access

### Recommended
- **Python:** 3.11+
- **RAM:** 16GB (for 7B parameter LLM)
- **Storage:** 20GB
- **Network:** Ethernet for stability
- **GPU:** Optional, for faster LLM inference

### Software Dependencies
- **Ollama** or **LM Studio** for local LLM
- **Home Assistant** for IoT device control (optional but recommended)

---

## Installation

### Option 1: Direct Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Install requirements
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Option 2: Docker

```bash
# Build the image
docker build -t local-home-agent .

# Run the container
docker run -d -p 8000:8000 --name home-agent local-home-agent
```

### Option 3: Docker Compose

```bash
docker-compose up -d
```

---

## Configuration

### Main Configuration File

Copy `config/config.example.yaml` to `config/config.yaml` and customize:

```yaml
# Network Settings
network:
  host: "0.0.0.0"
  port: 8000

# Security Settings
security:
  admin_pin: "1234"  # CHANGE THIS!
  session_timeout: 30
  high_risk_actions:
    - door_unlock
    - alarm_control
    - camera_view
    - garage_open
    - lock_all

# Home Assistant Integration
home_assistant:
  url: "http://homeassistant.local:8123"
  token: "YOUR_LONG_LIVED_ACCESS_TOKEN"
  auto_discover: true

# LLM Configuration
llm:
  local:
    provider: "ollama"
    model: "llama3.2:3b"
    ollama_url: "http://localhost:11434"
```

### Environment Variables

```bash
# Optional overrides
export PASSPHRASE="your-secure-passphrase"
export ADMIN_PIN="5678"
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your-home-assistant-token"
```

---

## Role-Based Access Control

The system uses a hierarchical role structure where **Admin is the parent role**.

### Role Hierarchy

```
┌─────────────────────────────────────┐
│              ADMIN                  │  ← Full control (parent role)
│  • All permissions                  │
│  • User management                  │
│  • System configuration             │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│            OPERATOR                 │  ← Property manager
│  • Device control                   │
│  • User management                  │
│  • Guest invitations                │
│  • View audit logs                  │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│            RESIDENT                 │  ← Standard resident
│  • Control devices in their room    │
│  • Activate scenes                  │
│  • Chat with AI                     │
│  • Invite guests                    │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│             GUEST                   │  ← Temporary access
│  • Limited device control           │
│  • Chat only                        │
│  • Access expires after set hours   │
└─────────────────────────────────────┘
```

### Permission Types

| Permission | Description | Admin | Operator | Resident | Guest |
|------------|-------------|:-----:|:--------:|:--------:|:-----:|
| device_control | Full device control | ✅ | ✅ | ✅ | ❌ |
| device_control_limited | Basic device control | ✅ | ✅ | ✅ | ✅ |
| device_manage | Add/remove devices | ✅ | ✅ | ❌ | ❌ |
| scene_activate | Run automation scenes | ✅ | ✅ | ✅ | ❌ |
| lock_control | Control door locks | ✅ | ✅ | ❌ | ❌ |
| camera_view | View security cameras | ✅ | ✅ | ✅ | ❌ |
| user_manage | Create/modify users | ✅ | ✅ | ❌ | ❌ |
| guest_invite | Invite guests | ✅ | ✅ | ✅ | ❌ |
| broadcast_message | Message all users | ✅ | ✅ | ❌ | ❌ |
| chat | Use AI chat | ✅ | ✅ | ✅ | ✅ |

### Creating Users

**Via UI:** Settings → Users & Rooms → Add New User

**Via API:**
```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "role": "resident",
    "room_id": "room-101",
    "email": "john@example.com"
  }'
```

### Guest Invitations

Residents can invite guests with temporary access:

```bash
curl -X POST http://localhost:8000/api/guests/invite \
  -H "Content-Type: application/json" \
  -d '{
    "guest_name": "Visitor Name",
    "expiry_hours": 24,
    "room_access": "room-101"
  }'
```

Response includes an access token for the guest.

---

## IoT Device Integration

### Home Assistant (Recommended)

1. Install Home Assistant on your local network
2. Generate a Long-Lived Access Token:
   - Home Assistant → Profile → Long-Lived Access Tokens
3. Configure in `config.yaml`:
   ```yaml
   home_assistant:
     url: "http://homeassistant.local:8123"
     token: "YOUR_TOKEN_HERE"
   ```

### Supported Protocols (via Home Assistant)

- **Zigbee** - via Zigbee2MQTT or ZHA
- **Z-Wave** - via Z-Wave JS
- **Matter** - native support in HA
- **MQTT** - direct integration
- **WiFi** - various integrations
- **Thread** - via Matter

### Device Assignment

Devices can be assigned to:
1. **Rooms** - All occupants of the room can control the device
2. **Users** - Specific users get direct access
3. **Roles** - All users with that role can control

```bash
# Assign device to a room
curl -X POST http://localhost:8000/api/devices/assign \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "light.living_room",
    "device_name": "Living Room Light",
    "room_id": "room-101",
    "entity_id": "light.living_room"
  }'
```

### High-Risk Actions

Certain actions require additional verification:

- **door_unlock** - Unlock entry doors
- **alarm_control** - Arm/disarm security system
- **camera_view** - Access security cameras
- **garage_open** - Open garage doors
- **lock_all** - Lock all doors

Configure via Settings → Tools & Permissions or API.

---

## AI Model Setup

### Option 1: Ollama (Recommended)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2:3b    # 3B parameters, ~2GB
ollama pull llama3.2:1b    # 1B parameters, ~1.3GB (lighter)

# Start Ollama server
ollama serve
```

Configure in `config.yaml`:
```yaml
llm:
  local:
    provider: "ollama"
    model: "llama3.2:3b"
    ollama_url: "http://localhost:11434"
```

### Option 2: LM Studio

1. Download LM Studio from https://lmstudio.ai
2. Download a model (e.g., Llama 3.2)
3. Start the local server (port 1234)

Configure:
```yaml
llm:
  local:
    provider: "lmstudio"
    model: "local-model"
    lmstudio_url: "http://localhost:1234"
```

---

## Security Best Practices

### 1. Change Default Credentials
```yaml
security:
  admin_pin: "CHANGE_THIS_PIN"
```

### 2. Use Strong Passphrase
```bash
export PASSPHRASE="your-long-secure-passphrase-here"
```

### 3. Network Security
- Use WPA3 or WPA2 for WiFi
- Consider a dedicated IoT VLAN
- Enable firewall rules

### 4. Regular Updates
```bash
cd local-home-agent
git pull origin main
pip install -r requirements.txt --upgrade
```

### 5. Audit Logging
All security events are logged to `logs/audit.log`:
- Login attempts
- High-risk actions
- Permission changes
- User creation/deletion

---

## API Reference

### Authentication & Users

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/users` | GET | List all users |
| `/api/users` | POST | Create new user |
| `/api/users/{id}` | GET | Get user details |
| `/api/users/{id}` | PUT | Update user |
| `/api/users/{id}` | DELETE | Deactivate user |
| `/api/users/{id}/permissions` | GET | Get user permissions |

### Rooms & Devices

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rooms` | GET | List all rooms |
| `/api/rooms/{id}` | GET | Get room details |
| `/api/devices/assignments` | GET | List device assignments |
| `/api/devices/assign` | POST | Assign device to room/user |
| `/api/devices/user/{id}` | GET | Get user's devices |

### Messaging

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/messages` | POST | Send message |
| `/api/messages/broadcast` | POST | Broadcast to all |
| `/api/messages/{user_id}` | GET | Get user's messages |

### Guests

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/guests/invite` | POST | Invite guest |
| `/api/guests` | GET | List active guests |
| `/api/guests/{id}` | DELETE | Revoke guest access |

### AI & Verification

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/verify/passphrase` | POST | Verify with agentic swarm |
| `/api/verify/prompt-chain` | POST | 4-stage verification |
| `/api/reason/thermodynamic` | POST | Thermodynamic reasoning |

---

## Troubleshooting

### LLM Not Responding

```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

### Home Assistant Connection Failed

1. Verify URL is accessible: `curl http://homeassistant.local:8123/api/`
2. Check token is valid (regenerate if needed)
3. Ensure HA is on same network

### Permission Denied Errors

1. Check user's role has required permission
2. Verify user is active and not expired
3. Check if action is in high-risk list

### Device Control Not Working

1. Verify device is assigned to user's room
2. Check Home Assistant entity_id is correct
3. Test directly in HA first

### Reset to Defaults

```bash
# Clear local storage (browser)
localStorage.clear()

# Reset server state
rm -rf logs/*
# Restart server
```

---

## Support

- **GitHub Issues:** https://github.com/Fix-It-For-Me-AI/local-home-agent/issues
- **Documentation:** https://docs.fixitforme.ai/local-agent
- **Email:** support@fixitforme.ai

---

*Built with ❤️ by FixItForMe.ai*
