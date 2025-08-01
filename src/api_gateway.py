"""
API Gateway for Travel Agent System.

This gateway provides a single entry point for clients to interact with
the travel agent system. It handles:
- Client authentication (JWT tokens)
- Request routing to the orchestrator
- Rate limiting
- SSL/TLS termination
"""
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from fastapi import FastAPI, HTTPException, Depends, Security, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

from .security.auth import security_manager, rate_limit
from .agents.orchestrator.remote_agent_connection import RemoteAgentConnection


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Configuration
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:10001")
API_GATEWAY_PORT = int(os.getenv("API_GATEWAY_PORT", "8080"))


# FastAPI app
app = FastAPI(
    title="Travel Agent System API",
    description="API Gateway for the Travel Agent System",
    version="1.0.0"
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security
security = HTTPBearer()


# Request/Response models
class AuthRequest(BaseModel):
    """Authentication request."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class AuthResponse(BaseModel):
    """Authentication response."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TravelRequest(BaseModel):
    """Travel planning request."""
    message: str = Field(..., description="User's travel request")
    context_id: Optional[str] = Field(None, description="Context ID for conversation continuity")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class TravelResponse(BaseModel):
    """Travel planning response."""
    status: str = Field(..., description="Request status")
    task_id: str = Field(..., description="Task ID for tracking")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


class UserSession(BaseModel):
    """User session information."""
    user_id: str
    username: str
    roles: list[str]
    session_id: str


# Dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> UserSession:
    """Get the current authenticated user."""
    token = credentials.credentials
    payload = security_manager.verify_jwt_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Extract user info from token
    return UserSession(
        user_id=payload.get("sub", ""),
        username=payload.get("username", ""),
        roles=payload.get("roles", ["user"]),
        session_id=payload.get("session_id", str(uuid.uuid4()))
    )


async def check_rate_limit(user: UserSession = Depends(get_current_user)):
    """Check rate limit for the user."""
    if not security_manager.check_rate_limit(user.user_id, limit=120):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return user


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "api_gateway"}


@app.post("/auth/login", response_model=AuthResponse)
async def login(auth_request: AuthRequest):
    """Authenticate user and return JWT tokens."""
    # In production, verify credentials against database
    # For now, we'll create a demo user
    if auth_request.username == "demo" and auth_request.password == "demo123":
        # Create user payload
        user_data = {
            "sub": f"user_{uuid.uuid4().hex[:8]}",
            "username": auth_request.username,
            "roles": ["user"],
            "session_id": security_manager.generate_session_id()
        }
        
        # Create tokens
        access_token = security_manager.create_jwt_token(
            user_data,
            expires_delta=timedelta(minutes=30)
        )
        
        refresh_token = security_manager.create_jwt_token(
            {**user_data, "type": "refresh"},
            expires_delta=timedelta(days=7)
        )
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=1800  # 30 minutes
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/auth/refresh", response_model=AuthResponse)
async def refresh_token(
    authorization: str = Header(..., description="Bearer refresh_token")
):
    """Refresh access token using refresh token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    refresh_token = authorization.split(" ")[1]
    payload = security_manager.verify_jwt_token(refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Create new access token
    user_data = {
        "sub": payload["sub"],
        "username": payload["username"],
        "roles": payload["roles"],
        "session_id": payload["session_id"]
    }
    
    new_access_token = security_manager.create_jwt_token(
        user_data,
        expires_delta=timedelta(minutes=30)
    )
    
    return AuthResponse(
        access_token=new_access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800
    )


@app.post("/travel/plan", response_model=TravelResponse)
async def plan_travel(
    request: TravelRequest,
    user: UserSession = Depends(check_rate_limit)
):
    """Submit a travel planning request."""
    try:
        # Add authentication headers for orchestrator
        headers = {}
        headers = await security_manager.security_manager.add_auth_header(headers)
        
        # Create A2A message format
        a2a_request = {
            "message": {
                "parts": [{"text": request.message}],
                "context_id": request.context_id or str(uuid.uuid4())
            },
            "metadata": {
                "user_id": user.user_id,
                "username": user.username,
                "session_id": user.session_id,
                **(request.metadata or {})
            }
        }
        
        # Send to orchestrator
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/send_message",
                json=a2a_request,
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Orchestrator error: {response.text}"
                )
            
            result = response.json()
            
            return TravelResponse(
                status="submitted",
                task_id=result.get("task_id", str(uuid.uuid4())),
                message="Your travel planning request has been submitted",
                data=result
            )
            
    except httpx.RequestError as e:
        logger.error(f"Error connecting to orchestrator: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/travel/status/{task_id}")
async def get_task_status(
    task_id: str,
    user: UserSession = Depends(get_current_user)
):
    """Get the status of a travel planning task."""
    try:
        # Add authentication headers
        headers = {}
        headers = await security_manager.security_manager.add_auth_header(headers)
        
        # Query orchestrator for task status
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{ORCHESTRATOR_URL}/tasks/{task_id}",
                headers=headers
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Task not found")
            elif response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error retrieving task: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Error connecting to orchestrator: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


@app.get("/agents")
async def list_agents(user: UserSession = Depends(get_current_user)):
    """List all available agents in the system."""
    agents = [
        {
            "name": "Orchestrator",
            "description": "Coordinates all travel planning activities",
            "status": "active",
            "capabilities": ["planning", "coordination", "task_distribution"]
        },
        {
            "name": "Hotel Agent",
            "description": "Finds and books accommodations",
            "status": "active",
            "capabilities": ["hotel_search", "price_comparison", "booking"]
        },
        {
            "name": "Transport Agent",
            "description": "Arranges flights and transportation",
            "status": "active",
            "capabilities": ["flight_search", "route_planning", "booking"]
        },
        {
            "name": "Budget Agent",
            "description": "Manages travel budget and expenses",
            "status": "active",
            "capabilities": ["budget_tracking", "expense_validation", "cost_optimization"]
        }
    ]
    
    return {"agents": agents}


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {
        "error": "Internal server error",
        "status_code": 500,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    
    logger.info(f"Starting API Gateway on port {API_GATEWAY_PORT}")
    logger.info(f"Orchestrator URL: {ORCHESTRATOR_URL}")
    logger.info(f"SSL/TLS: {'Enabled' if use_ssl else 'Disabled'}")
    
    # Prepare SSL config if enabled
    ssl_config = {}
    if use_ssl:
        from .security.auth import get_ssl_context
        ssl_context = get_ssl_context()
        ssl_config = {
            "ssl_keyfile": os.getenv("SSL_KEY_FILE", "certs/server.key"),
            "ssl_certfile": os.getenv("SSL_CERT_FILE", "certs/server.crt"),
        }
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=API_GATEWAY_PORT,
        log_level="info",
        **ssl_config
    )