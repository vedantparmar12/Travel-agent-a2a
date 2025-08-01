"""
JWT Authentication and Security for A2A Travel Agent System.
"""
import os
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import logging
from functools import wraps
import asyncio

from cryptography.fernet import Fernet
from passlib.context import CryptContext
from dotenv import load_dotenv


load_dotenv()
logger = logging.getLogger(__name__)


# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
API_KEY_HEADER = "X-API-Key"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption for sensitive data
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


class SecurityManager:
    """Manages security operations for the travel agent system."""
    
    def __init__(self):
        self.service_accounts = self._load_service_accounts()
        self.api_keys = self._load_api_keys()
        self.rate_limits = {}
    
    def _load_service_accounts(self) -> Dict[str, Dict[str, Any]]:
        """Load service accounts for inter-agent communication."""
        return {
            "orchestrator": {
                "id": "orchestrator-agent",
                "name": "Orchestrator Agent",
                "roles": ["orchestrator", "agent"],
                "api_key": os.getenv("ORCHESTRATOR_API_KEY", self._generate_api_key("orchestrator"))
            },
            "hotel": {
                "id": "hotel-agent",
                "name": "Hotel Agent",
                "roles": ["agent", "hotel_specialist"],
                "api_key": os.getenv("HOTEL_API_KEY", self._generate_api_key("hotel"))
            },
            "transport": {
                "id": "transport-agent",
                "name": "Transport Agent",
                "roles": ["agent", "transport_specialist"],
                "api_key": os.getenv("TRANSPORT_API_KEY", self._generate_api_key("transport"))
            },
            "budget": {
                "id": "budget-agent",
                "name": "Budget Agent",
                "roles": ["agent", "budget_manager"],
                "api_key": os.getenv("BUDGET_API_KEY", self._generate_api_key("budget"))
            }
        }
    
    def _load_api_keys(self) -> Dict[str, str]:
        """Load API keys for external services."""
        return {
            "orchestrator": self.service_accounts["orchestrator"]["api_key"],
            "hotel": self.service_accounts["hotel"]["api_key"],
            "transport": self.service_accounts["transport"]["api_key"],
            "budget": self.service_accounts["budget"]["api_key"],
            # Client API keys
            "client": os.getenv("CLIENT_API_KEY", self._generate_api_key("client"))
        }
    
    def _generate_api_key(self, service: str) -> str:
        """Generate a secure API key for a service."""
        return f"{service}-{secrets.token_urlsafe(32)}"
    
    def create_jwt_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
    
    def create_service_token(self, service_id: str) -> str:
        """Create a JWT token for inter-agent communication."""
        service = self.service_accounts.get(service_id)
        if not service:
            raise ValueError(f"Unknown service: {service_id}")
        
        token_data = {
            "sub": service["id"],
            "name": service["name"],
            "roles": service["roles"],
            "type": "service"
        }
        
        return self.create_jwt_token(token_data, expires_delta=timedelta(hours=1))
    
    def verify_api_key(self, api_key: str) -> Optional[str]:
        """Verify an API key and return the associated service."""
        for service, key in self.api_keys.items():
            if secrets.compare_digest(key, api_key):
                return service
        return None
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        return fernet.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        return fernet.decrypt(encrypted_data.encode()).decode()
    
    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def check_rate_limit(self, client_id: str, limit: int = 60) -> bool:
        """Check if client has exceeded rate limit."""
        now = datetime.now()
        minute_key = now.strftime("%Y-%m-%d-%H-%M")
        
        if client_id not in self.rate_limits:
            self.rate_limits[client_id] = {}
        
        if minute_key not in self.rate_limits[client_id]:
            self.rate_limits[client_id] = {minute_key: 1}
            return True
        
        self.rate_limits[client_id][minute_key] += 1
        return self.rate_limits[client_id][minute_key] <= limit
    
    def generate_session_id(self) -> str:
        """Generate a secure session ID."""
        return secrets.token_urlsafe(32)


# Global security manager instance
security_manager = SecurityManager()


# Decorators for securing endpoints
def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    async def decorated_function(request, *args, **kwargs):
        api_key = request.headers.get(API_KEY_HEADER)
        if not api_key:
            return {"error": "API key required"}, 401
        
        service = security_manager.verify_api_key(api_key)
        if not service:
            return {"error": "Invalid API key"}, 401
        
        # Add service info to request
        request.state.service = service
        return await f(request, *args, **kwargs)
    
    return decorated_function


def require_jwt_token(f):
    """Decorator to require JWT token authentication."""
    @wraps(f)
    async def decorated_function(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"error": "JWT token required"}, 401
        
        token = auth_header.split(" ")[1]
        payload = security_manager.verify_jwt_token(token)
        if not payload:
            return {"error": "Invalid or expired token"}, 401
        
        # Add user info to request
        request.state.user = payload
        return await f(request, *args, **kwargs)
    
    return decorated_function


def rate_limit(requests_per_minute: int = 60):
    """Decorator to apply rate limiting."""
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            # Get client identifier
            client_id = getattr(request.state, 'service', None) or \
                       getattr(request.state, 'user', {}).get('sub', None) or \
                       request.client.host
            
            if not security_manager.check_rate_limit(client_id, requests_per_minute):
                return {"error": "Rate limit exceeded"}, 429
            
            return await f(request, *args, **kwargs)
        
        return decorated_function
    return decorator


# Security middleware for A2A communication
class A2ASecurityMiddleware:
    """Middleware to add security to A2A agent communication."""
    
    def __init__(self, service_id: str):
        self.service_id = service_id
        self.security_manager = security_manager
    
    async def add_auth_header(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Add authentication headers for outgoing requests."""
        # Add API key
        service = self.security_manager.service_accounts.get(self.service_id)
        if service:
            headers[API_KEY_HEADER] = service["api_key"]
        
        # Add JWT token
        token = self.security_manager.create_service_token(self.service_id)
        headers["Authorization"] = f"Bearer {token}"
        
        return headers
    
    async def verify_incoming_request(self, headers: Dict[str, str]) -> Tuple[bool, Optional[str]]:
        """Verify authentication for incoming requests."""
        # Check API key
        api_key = headers.get(API_KEY_HEADER)
        if api_key:
            service = self.security_manager.verify_api_key(api_key)
            if service:
                return True, service
        
        # Check JWT token
        auth_header = headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = self.security_manager.verify_jwt_token(token)
            if payload:
                return True, payload.get("sub")
        
        return False, None


# Secure configuration loader
class SecureConfig:
    """Securely load and manage configuration."""
    
    @staticmethod
    def load_encrypted_config(file_path: str) -> Dict[str, Any]:
        """Load encrypted configuration file."""
        try:
            with open(file_path, 'r') as f:
                encrypted_content = f.read()
            
            decrypted_content = security_manager.decrypt_sensitive_data(encrypted_content)
            import json
            return json.loads(decrypted_content)
        except Exception as e:
            logger.error(f"Failed to load encrypted config: {e}")
            return {}
    
    @staticmethod
    def save_encrypted_config(config: Dict[str, Any], file_path: str):
        """Save configuration in encrypted format."""
        try:
            import json
            json_content = json.dumps(config, indent=2)
            encrypted_content = security_manager.encrypt_sensitive_data(json_content)
            
            with open(file_path, 'w') as f:
                f.write(encrypted_content)
        except Exception as e:
            logger.error(f"Failed to save encrypted config: {e}")


# SSL/TLS Configuration
def get_ssl_context():
    """Get SSL context for HTTPS."""
    import ssl
    
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    # Load certificates (in production, use real certificates)
    cert_file = os.getenv("SSL_CERT_FILE", "certs/server.crt")
    key_file = os.getenv("SSL_KEY_FILE", "certs/server.key")
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        context.load_cert_chain(cert_file, key_file)
    else:
        logger.warning("SSL certificates not found, generating self-signed certificate")
        # In production, this should not happen
        _generate_self_signed_cert(cert_file, key_file)
        context.load_cert_chain(cert_file, key_file)
    
    return context


def _generate_self_signed_cert(cert_file: str, key_file: str):
    """Generate self-signed certificate for development."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    # Generate key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Generate certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"CA"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Travel Agent System"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(u"localhost"),
            x509.DNSName(u"127.0.0.1"),
        ]),
        critical=False,
    ).sign(key, hashes.SHA256())
    
    # Create directories if needed
    os.makedirs(os.path.dirname(cert_file), exist_ok=True)
    
    # Write private key
    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Write certificate
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))