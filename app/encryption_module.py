"""
End-to-End Encryption Module (P4 D2.6)
Provides secure encryption for sensitive data and communications
"""

import os
import base64
import hashlib
import hmac
import secrets
import json
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


@dataclass
class EncryptedData:
    """Container for encrypted data with metadata"""
    ciphertext: bytes
    iv: bytes
    salt: bytes
    tag: Optional[bytes] = None
    algorithm: str = "AES-256-GCM"
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "iv": base64.b64encode(self.iv).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "tag": base64.b64encode(self.tag).decode() if self.tag else None,
            "algorithm": self.algorithm,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
    
    def to_string(self) -> str:
        """Serialize to string for storage"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedData":
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            iv=base64.b64decode(data["iv"]),
            salt=base64.b64decode(data["salt"]),
            tag=base64.b64decode(data["tag"]) if data.get("tag") else None,
            algorithm=data.get("algorithm", "AES-256-GCM"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None
        )
    
    @classmethod
    def from_string(cls, s: str) -> "EncryptedData":
        return cls.from_dict(json.loads(s))


@dataclass
class KeyPair:
    """RSA key pair for asymmetric encryption"""
    private_key: bytes
    public_key: bytes
    key_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class KeyDerivation:
    """Key derivation functions"""
    
    @staticmethod
    def derive_key(
        password: str,
        salt: bytes,
        key_length: int = 32,
        iterations: int = 100000
    ) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    @staticmethod
    def generate_salt(length: int = 16) -> bytes:
        """Generate random salt"""
        return os.urandom(length)
    
    @staticmethod
    def generate_iv(length: int = 12) -> bytes:
        """Generate random IV for AES-GCM (12 bytes)"""
        return os.urandom(length)


class SymmetricEncryption:
    """AES-256-GCM symmetric encryption"""
    
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or os.environ.get("ENCRYPTION_KEY", secrets.token_hex(32))
    
    def encrypt(
        self,
        plaintext: str,
        password: Optional[str] = None
    ) -> EncryptedData:
        """Encrypt plaintext using AES-256-GCM"""
        # Generate random salt and IV
        salt = KeyDerivation.generate_salt()
        iv = KeyDerivation.generate_iv()
        
        # Derive key from password or use master key
        if password:
            key = KeyDerivation.derive_key(password, salt)
        else:
            key = KeyDerivation.derive_key(self.master_key, salt)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Encrypt
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        
        return EncryptedData(
            ciphertext=ciphertext,
            iv=iv,
            salt=salt,
            tag=encryptor.tag,
            algorithm="AES-256-GCM",
            timestamp=datetime.now()
        )
    
    def decrypt(
        self,
        encrypted: EncryptedData,
        password: Optional[str] = None
    ) -> str:
        """Decrypt ciphertext using AES-256-GCM"""
        # Derive key
        if password:
            key = KeyDerivation.derive_key(password, encrypted.salt)
        else:
            key = KeyDerivation.derive_key(self.master_key, encrypted.salt)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(encrypted.iv, encrypted.tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt
        plaintext = decryptor.update(encrypted.ciphertext) + decryptor.finalize()
        
        return plaintext.decode()
    
    def encrypt_json(
        self,
        data: Dict[str, Any],
        password: Optional[str] = None
    ) -> EncryptedData:
        """Encrypt JSON data"""
        return self.encrypt(json.dumps(data), password)
    
    def decrypt_json(
        self,
        encrypted: EncryptedData,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Decrypt to JSON"""
        return json.loads(self.decrypt(encrypted, password))


class AsymmetricEncryption:
    """RSA asymmetric encryption for key exchange"""
    
    def __init__(self, key_size: int = 2048):
        self.key_size = key_size
        self.key_pairs: Dict[str, KeyPair] = {}
    
    def generate_key_pair(
        self,
        key_id: Optional[str] = None,
        expiry_days: int = 365
    ) -> KeyPair:
        """Generate new RSA key pair"""
        key_id = key_id or f"key_{secrets.token_hex(8)}"
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
            backend=default_backend()
        )
        
        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        key_pair = KeyPair(
            private_key=private_pem,
            public_key=public_pem,
            key_id=key_id,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=expiry_days)
        )
        
        self.key_pairs[key_id] = key_pair
        logger.info(f"Generated key pair: {key_id}")
        
        return key_pair
    
    def encrypt_with_public_key(
        self,
        plaintext: str,
        public_key_pem: bytes
    ) -> bytes:
        """Encrypt data with public key"""
        public_key = serialization.load_pem_public_key(
            public_key_pem,
            backend=default_backend()
        )
        
        ciphertext = public_key.encrypt(
            plaintext.encode(),
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return ciphertext
    
    def decrypt_with_private_key(
        self,
        ciphertext: bytes,
        key_id: str
    ) -> str:
        """Decrypt data with private key"""
        if key_id not in self.key_pairs:
            raise ValueError(f"Key not found: {key_id}")
        
        key_pair = self.key_pairs[key_id]
        
        private_key = serialization.load_pem_private_key(
            key_pair.private_key,
            password=None,
            backend=default_backend()
        )
        
        plaintext = private_key.decrypt(
            ciphertext,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return plaintext.decode()
    
    def get_public_key(self, key_id: str) -> Optional[bytes]:
        """Get public key for sharing"""
        if key_id in self.key_pairs:
            return self.key_pairs[key_id].public_key
        return None


class SecureTokenManager:
    """Manage secure tokens for authentication"""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = (secret_key or secrets.token_hex(32)).encode()
        self.active_tokens: Dict[str, Dict[str, Any]] = {}
    
    def generate_token(
        self,
        payload: Dict[str, Any],
        expiry_minutes: int = 60
    ) -> str:
        """Generate a secure token"""
        token_id = secrets.token_urlsafe(32)
        
        token_data = {
            "id": token_id,
            "payload": payload,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=expiry_minutes)).isoformat()
        }
        
        # Create signature
        message = json.dumps(token_data, sort_keys=True).encode()
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        
        # Store token
        self.active_tokens[token_id] = {
            **token_data,
            "signature": signature
        }
        
        # Return token as base64
        token_string = base64.urlsafe_b64encode(
            json.dumps({"id": token_id, "sig": signature[:16]}).encode()
        ).decode()
        
        return token_string
    
    def validate_token(self, token_string: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Validate a token and return payload"""
        try:
            # Decode token
            token_json = base64.urlsafe_b64decode(token_string.encode()).decode()
            token_info = json.loads(token_json)
            
            token_id = token_info.get("id")
            if not token_id or token_id not in self.active_tokens:
                return False, None
            
            stored = self.active_tokens[token_id]
            
            # Check expiry
            expires_at = datetime.fromisoformat(stored["expires_at"])
            if datetime.now() > expires_at:
                del self.active_tokens[token_id]
                return False, None
            
            # Verify signature prefix matches
            if not stored["signature"].startswith(token_info.get("sig", "")):
                return False, None
            
            return True, stored["payload"]
            
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False, None
    
    def revoke_token(self, token_string: str) -> bool:
        """Revoke a token"""
        try:
            token_json = base64.urlsafe_b64decode(token_string.encode()).decode()
            token_info = json.loads(token_json)
            token_id = token_info.get("id")
            
            if token_id and token_id in self.active_tokens:
                del self.active_tokens[token_id]
                return True
            return False
        except Exception:
            return False
    
    def cleanup_expired(self):
        """Remove expired tokens"""
        now = datetime.now()
        expired = [
            tid for tid, data in self.active_tokens.items()
            if datetime.fromisoformat(data["expires_at"]) < now
        ]
        for tid in expired:
            del self.active_tokens[tid]


class SecureVault:
    """Secure storage for sensitive data"""
    
    def __init__(
        self,
        storage_path: str = "config/vault",
        master_password: Optional[str] = None
    ):
        self.storage_path = storage_path
        self.encryption = SymmetricEncryption(master_password or secrets.token_hex(32))
        self.vault_data: Dict[str, EncryptedData] = {}
        self._load_vault()
    
    def _load_vault(self):
        """Load encrypted data from storage"""
        vault_file = os.path.join(self.storage_path, "vault.json")
        if os.path.exists(vault_file):
            try:
                with open(vault_file) as f:
                    data = json.load(f)
                    for key, encrypted_dict in data.items():
                        self.vault_data[key] = EncryptedData.from_dict(encrypted_dict)
            except Exception as e:
                logger.error(f"Failed to load vault: {e}")
    
    def _save_vault(self):
        """Save encrypted data to storage"""
        os.makedirs(self.storage_path, exist_ok=True)
        vault_file = os.path.join(self.storage_path, "vault.json")
        
        data = {key: enc.to_dict() for key, enc in self.vault_data.items()}
        with open(vault_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def store(self, key: str, value: Any):
        """Store a value securely"""
        if isinstance(value, dict):
            encrypted = self.encryption.encrypt_json(value)
        else:
            encrypted = self.encryption.encrypt(str(value))
        
        self.vault_data[key] = encrypted
        self._save_vault()
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a stored value"""
        if key not in self.vault_data:
            return None
        
        try:
            return self.encryption.decrypt(self.vault_data[key])
        except Exception as e:
            logger.error(f"Failed to decrypt {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a stored value"""
        if key in self.vault_data:
            del self.vault_data[key]
            self._save_vault()
            return True
        return False
    
    def list_keys(self) -> list:
        """List all stored keys"""
        return list(self.vault_data.keys())


# FastAPI routes
def create_encryption_routes():
    """Create FastAPI routes for encryption services"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/api/security", tags=["security"])
    
    encryption = SymmetricEncryption()
    token_manager = SecureTokenManager()
    vault = SecureVault()
    
    class EncryptRequest(BaseModel):
        plaintext: str
        password: Optional[str] = None
    
    class DecryptRequest(BaseModel):
        encrypted_data: Dict[str, Any]
        password: Optional[str] = None
    
    class TokenRequest(BaseModel):
        payload: Dict[str, Any]
        expiry_minutes: int = 60
    
    class VaultStoreRequest(BaseModel):
        key: str
        value: Any
    
    @router.post("/encrypt")
    async def encrypt_data(request: EncryptRequest):
        """Encrypt data"""
        encrypted = encryption.encrypt(request.plaintext, request.password)
        return {"encrypted": encrypted.to_dict()}
    
    @router.post("/decrypt")
    async def decrypt_data(request: DecryptRequest):
        """Decrypt data"""
        try:
            encrypted = EncryptedData.from_dict(request.encrypted_data)
            plaintext = encryption.decrypt(encrypted, request.password)
            return {"plaintext": plaintext}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")
    
    @router.post("/token/generate")
    async def generate_token(request: TokenRequest):
        """Generate a secure token"""
        token = token_manager.generate_token(request.payload, request.expiry_minutes)
        return {"token": token}
    
    @router.post("/token/validate")
    async def validate_token(token: str):
        """Validate a token"""
        valid, payload = token_manager.validate_token(token)
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {"valid": True, "payload": payload}
    
    @router.post("/token/revoke")
    async def revoke_token(token: str):
        """Revoke a token"""
        if token_manager.revoke_token(token):
            return {"success": True}
        raise HTTPException(status_code=404, detail="Token not found")
    
    @router.post("/vault/store")
    async def store_in_vault(request: VaultStoreRequest):
        """Store value in secure vault"""
        vault.store(request.key, request.value)
        return {"success": True}
    
    @router.get("/vault/retrieve/{key}")
    async def retrieve_from_vault(key: str):
        """Retrieve value from secure vault"""
        value = vault.retrieve(key)
        if value is None:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"value": value}
    
    @router.delete("/vault/{key}")
    async def delete_from_vault(key: str):
        """Delete value from secure vault"""
        if vault.delete(key):
            return {"success": True}
        raise HTTPException(status_code=404, detail="Key not found")
    
    @router.get("/vault/keys")
    async def list_vault_keys():
        """List all keys in vault"""
        return {"keys": vault.list_keys()}
    
    return router
