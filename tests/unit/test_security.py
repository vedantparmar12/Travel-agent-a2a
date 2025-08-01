"""
Unit tests for security module.
"""
import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from src.security.auth import (
    SecurityManager,
    A2ASecurityMiddleware,
    SecureConfig,
    API_KEY_HEADER
)


class TestSecurityManager:
    """Test cases for SecurityManager."""
    
    @pytest.fixture
    def security_manager(self):
        """Create a SecurityManager instance for testing."""
        return SecurityManager()
    
    def test_generate_api_key(self, security_manager):
        """Test API key generation."""
        api_key = security_manager._generate_api_key("test-service")
        
        assert api_key.startswith("test-service-")
        assert len(api_key) > 20  # Should have substantial random component
    
    def test_create_jwt_token(self, security_manager):
        """Test JWT token creation."""
        data = {"sub": "test-user", "role": "agent"}
        token = security_manager.create_jwt_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        decoded = jwt.decode(token, security_manager.SECRET_KEY, algorithms=[security_manager.ALGORITHM])
        assert decoded["sub"] == "test-user"
        assert decoded["role"] == "agent"
        assert "exp" in decoded
        assert "iat" in decoded
    
    def test_verify_jwt_token_valid(self, security_manager):
        """Test verifying a valid JWT token."""
        data = {"sub": "test-user", "role": "agent"}
        token = security_manager.create_jwt_token(data)
        
        result = security_manager.verify_jwt_token(token)
        assert result is not None
        assert result["sub"] == "test-user"
        assert result["role"] == "agent"
    
    def test_verify_jwt_token_expired(self, security_manager):
        """Test verifying an expired JWT token."""
        data = {"sub": "test-user", "role": "agent"}
        # Create token that expires immediately
        token = security_manager.create_jwt_token(data, expires_delta=timedelta(seconds=-1))
        
        result = security_manager.verify_jwt_token(token)
        assert result is None
    
    def test_verify_jwt_token_invalid(self, security_manager):
        """Test verifying an invalid JWT token."""
        result = security_manager.verify_jwt_token("invalid.token.here")
        assert result is None
    
    def test_create_service_token(self, security_manager):
        """Test creating a service token."""
        token = security_manager.create_service_token("hotel")
        
        assert isinstance(token, str)
        
        # Verify token contains service info
        decoded = security_manager.verify_jwt_token(token)
        assert decoded["sub"] == "hotel-agent"
        assert decoded["name"] == "Hotel Agent"
        assert "hotel_specialist" in decoded["roles"]
        assert decoded["type"] == "service"
    
    def test_verify_api_key_valid(self, security_manager):
        """Test verifying a valid API key."""
        # Get a known API key
        hotel_key = security_manager.api_keys["hotel"]
        
        result = security_manager.verify_api_key(hotel_key)
        assert result == "hotel"
    
    def test_verify_api_key_invalid(self, security_manager):
        """Test verifying an invalid API key."""
        result = security_manager.verify_api_key("invalid-api-key")
        assert result is None
    
    def test_encrypt_decrypt_data(self, security_manager):
        """Test data encryption and decryption."""
        original_data = "sensitive information"
        
        encrypted = security_manager.encrypt_sensitive_data(original_data)
        assert encrypted != original_data
        assert isinstance(encrypted, str)
        
        decrypted = security_manager.decrypt_sensitive_data(encrypted)
        assert decrypted == original_data
    
    def test_password_hashing(self, security_manager):
        """Test password hashing and verification."""
        password = "secure_password_123"
        
        hashed = security_manager.hash_password(password)
        assert hashed != password
        assert isinstance(hashed, str)
        
        # Verify correct password
        assert security_manager.verify_password(password, hashed) is True
        
        # Verify incorrect password
        assert security_manager.verify_password("wrong_password", hashed) is False
    
    def test_rate_limiting(self, security_manager):
        """Test rate limiting functionality."""
        client_id = "test-client"
        limit = 5
        
        # Should allow first requests
        for i in range(limit):
            assert security_manager.check_rate_limit(client_id, limit) is True
        
        # Should block after limit
        assert security_manager.check_rate_limit(client_id, limit) is False
    
    def test_generate_session_id(self, security_manager):
        """Test session ID generation."""
        session_id1 = security_manager.generate_session_id()
        session_id2 = security_manager.generate_session_id()
        
        assert isinstance(session_id1, str)
        assert len(session_id1) > 20
        assert session_id1 != session_id2  # Should be unique


class TestA2ASecurityMiddleware:
    """Test cases for A2A Security Middleware."""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        return A2ASecurityMiddleware("test-service")
    
    @pytest.mark.asyncio
    async def test_add_auth_header(self, middleware):
        """Test adding authentication headers."""
        headers = {}
        
        result = await middleware.add_auth_header(headers)
        
        assert API_KEY_HEADER in result
        assert "Authorization" in result
        assert result["Authorization"].startswith("Bearer ")
    
    @pytest.mark.asyncio
    async def test_verify_incoming_request_valid_api_key(self, middleware):
        """Test verifying request with valid API key."""
        # Get a valid API key
        valid_key = middleware.security_manager.api_keys["hotel"]
        headers = {API_KEY_HEADER: valid_key}
        
        is_valid, service = await middleware.verify_incoming_request(headers)
        
        assert is_valid is True
        assert service == "hotel"
    
    @pytest.mark.asyncio
    async def test_verify_incoming_request_valid_jwt(self, middleware):
        """Test verifying request with valid JWT."""
        token = middleware.security_manager.create_service_token("hotel")
        headers = {"Authorization": f"Bearer {token}"}
        
        is_valid, service = await middleware.verify_incoming_request(headers)
        
        assert is_valid is True
        assert service == "hotel-agent"
    
    @pytest.mark.asyncio
    async def test_verify_incoming_request_invalid(self, middleware):
        """Test verifying request with invalid credentials."""
        headers = {API_KEY_HEADER: "invalid-key"}
        
        is_valid, service = await middleware.verify_incoming_request(headers)
        
        assert is_valid is False
        assert service is None


class TestSecureConfig:
    """Test cases for SecureConfig."""
    
    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create a temporary config file."""
        return tmp_path / "test_config.enc"
    
    def test_save_and_load_encrypted_config(self, temp_config_file):
        """Test saving and loading encrypted configuration."""
        config_data = {
            "database_url": "postgresql://user:pass@localhost/db",
            "api_keys": {
                "service1": "key1",
                "service2": "key2"
            },
            "settings": {
                "debug": False,
                "port": 8080
            }
        }
        
        # Save encrypted config
        SecureConfig.save_encrypted_config(config_data, str(temp_config_file))
        
        # Load encrypted config
        loaded_config = SecureConfig.load_encrypted_config(str(temp_config_file))
        
        assert loaded_config == config_data
        assert loaded_config["database_url"] == config_data["database_url"]
        assert loaded_config["api_keys"] == config_data["api_keys"]
        assert loaded_config["settings"] == config_data["settings"]
    
    def test_load_nonexistent_config(self):
        """Test loading non-existent config file."""
        result = SecureConfig.load_encrypted_config("nonexistent.enc")
        assert result == {}