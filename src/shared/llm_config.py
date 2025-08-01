"""
Centralized LLM configuration for all agents.
"""
import os
from typing import Optional, Union
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

load_dotenv()


class LLMConfig:
    """Centralized configuration for LLM models across all agents."""
    
    # Available LLM providers
    PROVIDERS = {
        "gemini": "ChatGoogleGenerativeAI",
        "anthropic": "ChatAnthropic", 
        "openai": "ChatOpenAI"
    }
    
    # Default models for each provider
    DEFAULT_MODELS = {
        "gemini": "gemini-2.0-flash",
        "anthropic": "claude-3-5-sonnet-latest",
        "openai": "gpt-4o"
    }
    
    # Environment variable mapping
    API_KEY_ENV_VARS = {
        "gemini": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY"
    }
    
    @staticmethod
    def get_default_provider() -> str:
        """Get the default LLM provider based on available API keys."""
        # Priority order: Gemini > Anthropic > OpenAI
        if os.getenv("GOOGLE_API_KEY"):
            return "gemini"
        elif os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            return "openai"
        else:
            # Default to Gemini (will fail if no key provided)
            return "gemini"
    
    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Union[ChatGoogleGenerativeAI, ChatAnthropic, ChatOpenAI]:
        """
        Get an LLM instance based on configuration.
        
        Args:
            provider: The LLM provider to use (gemini, anthropic, openai)
            model: The specific model to use
            temperature: Model temperature
            **kwargs: Additional model parameters
            
        Returns:
            LLM instance
        """
        # Use default provider if not specified
        if provider is None:
            provider = LLMConfig.get_default_provider()
        
        # Validate provider
        if provider not in LLMConfig.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(LLMConfig.PROVIDERS.keys())}")
        
        # Use default model if not specified
        if model is None:
            model = LLMConfig.DEFAULT_MODELS.get(provider)
        
        # Check API key
        api_key_var = LLMConfig.API_KEY_ENV_VARS.get(provider)
        if not os.getenv(api_key_var):
            raise ValueError(f"Missing API key: {api_key_var}")
        
        # Create LLM instance
        if provider == "gemini":
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                **kwargs
            )
        elif provider == "anthropic":
            return ChatAnthropic(
                model=model,
                temperature=temperature,
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                **kwargs
            )
        elif provider == "openai":
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                **kwargs
            )
        else:
            raise ValueError(f"Provider {provider} not implemented")
    
    @staticmethod
    def get_agent_llm(agent_name: str, **kwargs) -> Union[ChatGoogleGenerativeAI, ChatAnthropic, ChatOpenAI]:
        """
        Get LLM for a specific agent with agent-specific configuration.
        
        Args:
            agent_name: Name of the agent
            **kwargs: Additional parameters
            
        Returns:
            LLM instance
        """
        # Agent-specific configurations (can be customized)
        agent_configs = {
            "orchestrator": {"provider": None, "temperature": 0.5},  # More deterministic
            "hotel": {"provider": None, "temperature": 0.7},
            "transport": {"provider": None, "temperature": 0.7},
            "activity": {"provider": None, "temperature": 0.8},  # More creative
            "budget": {"provider": None, "temperature": 0.3},  # Very deterministic
            "itinerary": {"provider": None, "temperature": 0.6}
        }
        
        # Get agent config
        config = agent_configs.get(agent_name.lower(), {})
        
        # Allow environment variable override for specific agents
        provider_override = os.getenv(f"{agent_name.upper()}_LLM_PROVIDER")
        if provider_override:
            config["provider"] = provider_override
        
        # Merge with kwargs
        config.update(kwargs)
        
        return LLMConfig.get_llm(**config)
    
    @staticmethod
    def check_api_keys() -> dict:
        """Check which API keys are available."""
        results = {}
        for provider, env_var in LLMConfig.API_KEY_ENV_VARS.items():
            api_key = os.getenv(env_var)
            results[provider] = {
                "env_var": env_var,
                "available": bool(api_key),
                "key_prefix": api_key[:10] + "..." if api_key else None
            }
        return results