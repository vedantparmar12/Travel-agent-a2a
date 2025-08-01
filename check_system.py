#!/usr/bin/env python3
"""
System readiness check for Travel Agent System.
"""
import os
import sys
import importlib
from dotenv import load_dotenv
from typing import Dict, List, Tuple
from pathlib import Path

# Load environment variables
load_dotenv()


class SystemChecker:
    """Check system readiness for deployment."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
    
    def check_python_version(self) -> bool:
        """Check Python version."""
        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            self.successes.append(f"✓ Python version {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            self.issues.append(f"✗ Python 3.8+ required, found {version.major}.{version.minor}")
            return False
    
    def check_dependencies(self) -> bool:
        """Check all required dependencies are installed."""
        required_packages = [
            ("langchain", "LangChain"),
            ("langchain_google_genai", "LangChain Google Generative AI"),
            ("langchain_anthropic", "LangChain Anthropic"),
            ("langchain_openai", "LangChain OpenAI"),
            ("langgraph", "LangGraph"),
            ("a2a", "A2A Protocol"),
            ("fastapi", "FastAPI"),
            ("pydantic", "Pydantic"),
            ("jwt", "PyJWT"),
            ("passlib", "Passlib"),
            ("cryptography", "Cryptography"),
            ("dotenv", "python-dotenv"),
            ("pytest", "Pytest"),
            ("aiohttp", "AioHTTP"),
            ("httpx", "HTTPX"),
            ("redis", "Redis (optional)"),
            ("sqlalchemy", "SQLAlchemy (optional)")
        ]
        
        all_good = True
        for package, name in required_packages:
            try:
                importlib.import_module(package)
                self.successes.append(f"✓ {name} installed")
            except ImportError:
                if "optional" in name:
                    self.warnings.append(f"⚠ {name} not installed")
                else:
                    self.issues.append(f"✗ {name} not installed")
                    all_good = False
        
        return all_good
    
    def check_api_keys(self) -> bool:
        """Check API keys configuration."""
        api_keys = {
            "GOOGLE_API_KEY": ("Google Gemini API", True),
            "ANTHROPIC_API_KEY": ("Anthropic Claude API", False),
            "OPENAI_API_KEY": ("OpenAI API", False),
            "JWT_SECRET_KEY": ("JWT Secret Key", True),
            "ENCRYPTION_KEY": ("Encryption Key", True)
        }
        
        has_llm_key = False
        all_required = True
        
        for key, (name, required) in api_keys.items():
            value = os.getenv(key)
            if value and value != f"your_{key.lower()}_here" and "change_in_production" not in value:
                self.successes.append(f"✓ {name} configured")
                if key in ["GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]:
                    has_llm_key = True
            else:
                if required:
                    self.issues.append(f"✗ {name} not configured properly")
                    all_required = False
                else:
                    self.warnings.append(f"⚠ {name} not configured (optional)")
        
        if not has_llm_key:
            self.issues.append("✗ At least one LLM API key required (Gemini, Anthropic, or OpenAI)")
            return False
        
        return all_required
    
    def check_agent_files(self) -> bool:
        """Check all agent files exist."""
        base_path = Path("src/agents")
        agents = ["orchestrator", "hotel", "transport", "activity", "budget", "itinerary"]
        
        all_good = True
        for agent in agents:
            agent_path = base_path / agent
            required_files = ["__init__.py", "__main__.py", "agent_executor.py"]
            
            if agent != "orchestrator":
                required_files.append(f"{agent}_agent_a2a.py")
            else:
                required_files.append("orchestrator_a2a.py")
            
            for file in required_files:
                file_path = agent_path / file
                if file_path.exists():
                    self.successes.append(f"✓ {agent}/{file} exists")
                else:
                    self.issues.append(f"✗ {agent}/{file} missing")
                    all_good = False
        
        return all_good
    
    def check_shared_modules(self) -> bool:
        """Check shared modules exist."""
        shared_path = Path("src/shared")
        required_files = ["__init__.py", "models.py", "state.py", "protocols.py", "llm_config.py"]
        
        all_good = True
        for file in required_files:
            file_path = shared_path / file
            if file_path.exists():
                self.successes.append(f"✓ shared/{file} exists")
            else:
                self.issues.append(f"✗ shared/{file} missing")
                all_good = False
        
        return all_good
    
    def check_security(self) -> bool:
        """Check security configuration."""
        security_path = Path("src/security")
        
        if (security_path / "__init__.py").exists() and (security_path / "auth.py").exists():
            self.successes.append("✓ Security module exists")
            
            # Check SSL configuration
            use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
            if use_ssl:
                cert_file = os.getenv("SSL_CERT_FILE", "certs/server.crt")
                key_file = os.getenv("SSL_KEY_FILE", "certs/server.key")
                
                if Path(cert_file).exists() and Path(key_file).exists():
                    self.successes.append("✓ SSL certificates configured")
                else:
                    self.warnings.append("⚠ SSL enabled but certificates not found")
            else:
                self.warnings.append("⚠ SSL disabled (not recommended for production)")
            
            return True
        else:
            self.issues.append("✗ Security module missing")
            return False
    
    def check_tests(self) -> bool:
        """Check test configuration."""
        test_path = Path("tests")
        pytest_ini = Path("pytest.ini")
        
        if test_path.exists() and pytest_ini.exists():
            self.successes.append("✓ Test structure exists")
            
            # Count test files
            test_files = list(test_path.rglob("test_*.py"))
            if test_files:
                self.successes.append(f"✓ Found {len(test_files)} test files")
            else:
                self.warnings.append("⚠ No test files found")
            
            return True
        else:
            self.issues.append("✗ Test configuration missing")
            return False
    
    def check_environment_files(self) -> bool:
        """Check environment files."""
        env_file = Path(".env")
        env_example = Path(".env.example")
        
        all_good = True
        
        if env_example.exists():
            self.successes.append("✓ .env.example exists")
        else:
            self.issues.append("✗ .env.example missing")
            all_good = False
        
        if env_file.exists():
            self.successes.append("✓ .env file exists")
        else:
            self.warnings.append("⚠ .env file missing (create from .env.example)")
        
        return all_good
    
    def check_documentation(self) -> bool:
        """Check documentation files."""
        docs = {
            "README.md": "Project README",
            "PLANNING.md": "Architecture documentation",
            "TASK.md": "Task tracking",
            "requirements.txt": "Python dependencies"
        }
        
        all_good = True
        for file, desc in docs.items():
            if Path(file).exists():
                self.successes.append(f"✓ {desc} exists")
            else:
                if file in ["PLANNING.md", "TASK.md"]:
                    self.warnings.append(f"⚠ {desc} missing (recommended)")
                else:
                    self.issues.append(f"✗ {desc} missing")
                    all_good = False
        
        return all_good
    
    def run_all_checks(self) -> bool:
        """Run all system checks."""
        print("🔍 Travel Agent System - Readiness Check")
        print("=" * 60)
        
        checks = [
            ("Python Version", self.check_python_version),
            ("Dependencies", self.check_dependencies),
            ("API Keys", self.check_api_keys),
            ("Agent Files", self.check_agent_files),
            ("Shared Modules", self.check_shared_modules),
            ("Security", self.check_security),
            ("Tests", self.check_tests),
            ("Environment Files", self.check_environment_files),
            ("Documentation", self.check_documentation)
        ]
        
        all_passed = True
        for name, check_func in checks:
            print(f"\n📋 Checking {name}...")
            if not check_func():
                all_passed = False
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        
        if self.successes:
            print(f"\n✅ Passed: {len(self.successes)} checks")
            for success in self.successes[:5]:  # Show first 5
                print(f"   {success}")
            if len(self.successes) > 5:
                print(f"   ... and {len(self.successes) - 5} more")
        
        if self.warnings:
            print(f"\n⚠️  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if self.issues:
            print(f"\n❌ Issues: {len(self.issues)}")
            for issue in self.issues:
                print(f"   {issue}")
        
        print("\n" + "=" * 60)
        
        if all_passed and not self.issues:
            print("✅ System is ready! All critical checks passed.")
            print("\n🚀 Next steps:")
            print("1. Set your Gemini API key in .env file")
            print("2. Run: python src/launch_agents.py")
            print("3. In another terminal: python src/travel_client.py")
            return True
        else:
            print("❌ System is not ready. Please fix the issues above.")
            print("\n🔧 To fix:")
            print("1. Install missing dependencies: pip install -r requirements.txt")
            print("2. Configure API keys in .env file")
            print("3. Ensure all required files exist")
            return False


def main():
    """Run system check."""
    checker = SystemChecker()
    
    # Also check LLM configuration
    try:
        from src.shared.llm_config import LLMConfig
        
        print("\n🤖 LLM Configuration Check")
        print("=" * 60)
        
        api_status = LLMConfig.check_api_keys()
        for provider, info in api_status.items():
            if info["available"]:
                print(f"✓ {provider.title()}: Available ({info['key_prefix']})")
            else:
                print(f"✗ {provider.title()}: Not configured ({info['env_var']})")
        
        default_provider = LLMConfig.get_default_provider()
        print(f"\nDefault LLM Provider: {default_provider}")
        
    except Exception as e:
        print(f"\n⚠️  Could not check LLM configuration: {e}")
    
    # Run all checks
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()