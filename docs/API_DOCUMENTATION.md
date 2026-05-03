# Local Home Agent - API Documentation

**Version:** 1.0.0 | **Base URL:** `http://localhost:8000`

---

## Overview

The Local Home Agent provides a RESTful API for managing users, rooms, devices, and AI-powered home automation. All responses are in JSON format.

---

## Authentication

Currently, the API uses query parameter authentication:
```
?admin_id=admin-001
```

For production, implement proper JWT or session-based authentication.

---

## Endpoints

### 1. User Management

#### List Users
```http
GET /api/users?role={role}&room_id={room_id}&active_only={bool}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| role | string | Filter by role: admin, operator, resident, guest |
| room_id | string | Filter by room |
| active_only | boolean | Only return active users (default: true) |

**Response:**
```json
{
  "users": [
    {
      "id": "user-abc123",
      "name": "John Smith",
      "role": "resident",
      "room_id": "room-101",
      "email": "john@example.com",
      "is_active": true,
      "created_at": "2025-12-09T10:00:00",
      "expires_at": null
    }
  ]
}
```

#### Create User
```http
POST /api/users
```

**Request Body:**
```json
{
  "name": "Jane Doe",
  "role": "resident",
  "room_id": "room-102",
  "email": "jane@example.com",
  "phone": "+1-555-1234",
  "expiry_hours": 24  // For guests only
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "id": "user-def456",
    "name": "Jane Doe",
    "role": "resident",
    "room_id": "room-102",
    "access_token": "abc123xyz..."
  }
}
```

#### Get User
```http
GET /api/users/{user_id}
```

#### Update User
```http
PUT /api/users/{user_id}
```

**Request Body:**
```json
{
  "name": "Jane Smith",
  "role": "operator",
  "room_id": "room-201"
}
```

#### Deactivate User
```http
DELETE /api/users/{user_id}
```

#### Get User Permissions
```http
GET /api/users/{user_id}/permissions
```

**Response:**
```json
{
  "user_id": "user-abc123",
  "permissions": [
    "device_control",
    "scene_activate",
    "chat",
    "view_cameras",
    "guest_invite"
  ]
}
```

#### Grant Permission
```http
POST /api/users/{user_id}/permissions/{permission}
```

#### Revoke Permission
```http
DELETE /api/users/{user_id}/permissions/{permission}
```

---

### 2. Room Management

#### List Rooms
```http
GET /api/rooms
```

**Response:**
```json
{
  "rooms": [
    {
      "id": "room-101",
      "name": "Room 101",
      "floor": 1,
      "building": null,
      "assigned_devices": ["light.room101", "switch.room101_fan"],
      "max_occupants": 1,
      "current_occupants": ["user-abc123"],
      "occupant_count": 1
    }
  ]
}
```

#### Get Room
```http
GET /api/rooms/{room_id}
```

**Response includes full occupant details.**

#### Assign User to Room
```http
POST /api/rooms/{room_id}/assign/{user_id}
```

---

### 3. Device Management

#### List Device Assignments
```http
GET /api/devices/assignments
```

**Response:**
```json
{
  "assignments": [
    {
      "device_id": "light.living_room",
      "device_name": "Living Room Light",
      "entity_id": "light.living_room",
      "assigned_to_room": "common-1",
      "assigned_to_users": [],
      "is_high_risk": false
    }
  ]
}
```

#### Assign Device
```http
POST /api/devices/assign
```

**Request Body:**
```json
{
  "device_id": "lock.front_door",
  "device_name": "Front Door Lock",
  "entity_id": "lock.front_door",
  "room_id": "common-1",
  "user_id": null,
  "is_high_risk": true
}
```

#### Get User's Devices
```http
GET /api/devices/user/{user_id}
```

**Response:**
```json
{
  "user_id": "user-abc123",
  "devices": [
    {
      "device_id": "light.room101",
      "device_name": "Room 101 Light",
      "entity_id": "light.room101",
      "is_high_risk": false
    }
  ]
}
```

#### Check Device Control Permission
```http
GET /api/devices/{device_id}/can-control/{user_id}
```

**Response:**
```json
{
  "device_id": "light.room101",
  "user_id": "user-abc123",
  "can_control": true
}
```

---

### 4. Messaging

#### Send Message
```http
POST /api/messages
```

**Request Body:**
```json
{
  "content": "Hello everyone!",
  "recipient_ids": ["user-abc123", "user-def456"],  // null for broadcast
  "message_type": "info",  // info, alert, warning, emergency
  "expires_hours": 24
}
```

#### Broadcast Message
```http
POST /api/messages/broadcast
```

**Request Body:**
```json
{
  "content": "Important announcement for all residents",
  "message_type": "alert"
}
```

#### Get User's Messages
```http
GET /api/messages/{user_id}?unread_only={bool}
```

**Response:**
```json
{
  "messages": [
    {
      "id": "msg-abc123",
      "sender_id": "admin-001",
      "sender_name": "Property Admin",
      "content": "Welcome to the co-living space!",
      "message_type": "info",
      "created_at": "2025-12-09T10:00:00",
      "read_by": []
    }
  ]
}
```

#### Mark Message Read
```http
POST /api/messages/{message_id}/read/{user_id}
```

---

### 5. Guest Management

#### Invite Guest
```http
POST /api/guests/invite
```

**Request Body:**
```json
{
  "guest_name": "Visitor Name",
  "expiry_hours": 24,
  "room_access": "room-101"
}
```

**Response:**
```json
{
  "success": true,
  "guest": {
    "id": "user-guest123",
    "name": "Visitor Name",
    "role": "guest",
    "room_id": "room-101"
  },
  "access_token": "secure-token-here...",
  "expires_at": "2025-12-10T10:00:00"
}
```

#### List Guests
```http
GET /api/guests
```

#### Revoke Guest
```http
DELETE /api/guests/{guest_id}
```

---

### 6. Roles & Permissions

#### List Available Roles
```http
GET /api/roles
```

**Response:**
```json
{
  "roles": [
    {
      "name": "admin",
      "permissions": ["*"],
      "inherits_from": ["operator", "resident", "guest"]
    },
    {
      "name": "resident",
      "permissions": ["device_control", "scene_activate", "chat", "view_cameras", "guest_invite"],
      "inherits_from": ["guest"]
    }
  ]
}
```

#### List Available Permissions
```http
GET /api/permissions
```

**Response:**
```json
{
  "permissions": [
    {"name": "device_control", "description": "Device Control"},
    {"name": "scene_activate", "description": "Scene Activate"},
    {"name": "lock_control", "description": "Lock Control"}
  ]
}
```

---

### 7. Admin Configuration

#### Get Admin Permissions Config
```http
GET /api/admin/permissions
```

#### Update Admin Permissions
```http
POST /api/admin/permissions
```

**Request Body:**
```json
{
  "high_risk_actions": ["door_unlock", "alarm_control"],
  "roles": {
    "resident": ["device_control", "chat"],
    "guest": ["chat"]
  },
  "guest_expiry_hours": 48,
  "device_allowlist": ["light.*", "switch.*"]
}
```

#### Check Permission
```http
GET /api/admin/check-permission?role={role}&permission={permission}
```

#### Check High-Risk Action
```http
GET /api/admin/is-high-risk?action={action}
```

---

### 8. AI Verification

#### Passphrase Verification (Agentic Swarm)
```http
POST /api/verify/passphrase
```

**Request Body:**
```json
{
  "passphrase": "user-entered-passphrase",
  "user_id": "user-abc123",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "success": true,
  "outcome": "PASS",
  "consensus_achieved": true,
  "reasoning": "All verification agents approved",
  "votes": {
    "approve": 3,
    "deny": 0,
    "abstain": 0,
    "challenge": 0
  },
  "energy_consumed": 15.5,
  "agent_votes": [
    {
      "agent": "verifier-001",
      "vote": "APPROVE",
      "confidence": 0.95,
      "reasoning": "Passphrase matches expected hash"
    }
  ]
}
```

#### Prompt Chain Verification
```http
POST /api/verify/prompt-chain
```

Uses 4-stage verification: Lexical → Semantic → Intent → Oracle

#### Thermodynamic Reasoning
```http
POST /api/reason/thermodynamic
```

**Request Body:**
```json
{
  "action_type": "door_unlock",
  "security_risk": 0.7,
  "behavior_surprise": 0.3,
  "resource_cost": 0.1,
  "hour": 3,
  "request_rate": 5
}
```

**Response:**
```json
{
  "success": true,
  "action": "VERIFY",
  "energy": 45.2,
  "current_state": "VIGILANT",
  "reasoning": "High security risk detected, verification required"
}
```

---

### 9. System

#### Health Check
```http
GET /api/health
```

#### Get Network Info
```http
GET /api/network/info
```

**Response:**
```json
{
  "local_ip": "192.168.1.100",
  "port": 8000,
  "hostname": "home-agent",
  "full_url": "http://192.168.1.100:8000",
  "access_token": "dynamic-hourly-token",
  "token_expires_in": 45
}
```

#### Export RBAC State
```http
GET /api/rbac/export
```

Returns full backup of users, rooms, devices, and messages.

---

## Error Handling

All errors return JSON with this structure:

```json
{
  "detail": "Error message here"
}
```

**HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid input)
- `403` - Forbidden (permission denied)
- `404` - Not Found
- `500` - Internal Server Error

---

## Rate Limiting

Default: 60 requests per minute per IP

Configure in `config.yaml`:
```yaml
security:
  rate_limit:
    enabled: true
    requests_per_minute: 60
    burst: 10
```

---

## WebSocket API

Connect to `/ws` for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// Send message
ws.send(JSON.stringify({
  type: 'chat',
  message: 'Hello'
}));
```

---

*Generated by Local Home Agent v1.0.0*
