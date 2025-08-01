"""
Launch all travel agents with security enabled.
"""
import asyncio
import subprocess
import sys
import time
import os
import signal
from typing import List, Dict
import logging
from dotenv import load_dotenv


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Enable SSL/TLS for all services
os.environ["USE_SSL"] = "true"


# Agent configuration with security
AGENTS = {
    "hotel": {
        "name": "Hotel Agent",
        "module": "src.agents.hotel",
        "port": 10010,
        "env_var": "HOTEL_AGENT_PORT"
    },
    "transport": {
        "name": "Transport Agent",
        "module": "src.agents.transport",
        "port": 10011,
        "env_var": "TRANSPORT_AGENT_PORT"
    },
    "budget": {
        "name": "Budget Agent",
        "module": "src.agents.budget",
        "port": 10013,
        "env_var": "BUDGET_AGENT_PORT"
    },
    "orchestrator": {
        "name": "Orchestrator Agent", 
        "module": "src.agents.orchestrator",
        "port": 10001,
        "env_var": "ORCHESTRATOR_AGENT_PORT",
        "depends_on": ["hotel", "transport", "budget"]
    },
    "api_gateway": {
        "name": "API Gateway",
        "module": "src.api_gateway",
        "port": 8080,
        "env_var": "API_GATEWAY_PORT",
        "depends_on": ["orchestrator"]
    }
}


class SecureAgentLauncher:
    """Manages launching and monitoring agent processes with security."""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = True
        self._generate_api_keys()
        self._setup_ssl_certificates()
    
    def _generate_api_keys(self):
        """Generate API keys for inter-agent communication if not set."""
        services = ["orchestrator", "hotel", "transport", "budget", "activity", "itinerary", "client"]
        
        for service in services:
            env_var = f"{service.upper()}_API_KEY"
            if not os.getenv(env_var):
                # Generate a secure API key
                import secrets
                api_key = f"{service}-{secrets.token_urlsafe(32)}"
                os.environ[env_var] = api_key
                logger.info(f"Generated API key for {service}")
    
    def _setup_ssl_certificates(self):
        """Ensure SSL certificates exist."""
        cert_dir = "certs"
        cert_file = os.path.join(cert_dir, "server.crt")
        key_file = os.path.join(cert_dir, "server.key")
        
        if not os.path.exists(cert_file) or not os.path.exists(key_file):
            logger.info("SSL certificates not found. They will be generated on first run.")
            os.makedirs(cert_dir, exist_ok=True)
    
    def start_agent(self, agent_id: str, config: Dict) -> subprocess.Popen:
        """Start a single agent process with security enabled."""
        agent_name = config["name"]
        module = config["module"]
        port = os.getenv(config["env_var"], config["port"])
        
        logger.info(f"Starting {agent_name} on port {port} (HTTPS)...")
        
        # Set environment variable for port
        env = os.environ.copy()
        env[config["env_var"]] = str(port)
        
        # Ensure SSL is enabled
        env["USE_SSL"] = "true"
        
        # Launch the agent
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Give it a moment to start
        time.sleep(3)
        
        # Check if it started successfully
        if process.poll() is None:
            logger.info(f"✓ {agent_name} started successfully (PID: {process.pid})")
        else:
            logger.error(f"✗ {agent_name} failed to start")
            stdout, stderr = process.communicate()
            if stdout:
                logger.error(f"STDOUT: {stdout}")
            if stderr:
                logger.error(f"STDERR: {stderr}")
        
        return process
    
    def start_all_agents(self):
        """Start all agents in the correct order."""
        # Start agents without dependencies first
        for agent_id, config in AGENTS.items():
            if "depends_on" not in config:
                self.processes[agent_id] = self.start_agent(agent_id, config)
        
        # Give base agents time to fully initialize
        logger.info("Waiting for base agents to initialize...")
        time.sleep(5)
        
        # Start agents with dependencies
        for agent_id, config in AGENTS.items():
            if "depends_on" in config:
                logger.info(f"Starting {config['name']} (depends on: {config['depends_on']})")
                self.processes[agent_id] = self.start_agent(agent_id, config)
                time.sleep(3)  # Extra time for dependent services
        
        logger.info("\nAll agents started with security enabled!")
        self.print_status()
    
    def print_status(self):
        """Print the status of all agents."""
        print("\n" + "="*70)
        print("SECURE TRAVEL AGENT SYSTEM STATUS")
        print("="*70)
        
        for agent_id, config in AGENTS.items():
            process = self.processes.get(agent_id)
            if process and process.poll() is None:
                port = os.getenv(config["env_var"], config["port"])
                print(f"✓ {config['name']:<20} Running on https://localhost:{port} (PID: {process.pid})")
            else:
                print(f"✗ {config['name']:<20} Not running")
        
        print("="*70)
        print("\nAPI Keys Generated:")
        for service in ["orchestrator", "hotel", "transport", "budget", "client"]:
            key = os.getenv(f"{service.upper()}_API_KEY", "Not set")
            print(f"- {service.capitalize():<15} {key[:20]}...")
        
        print("\nAccess points:")
        print(f"- API Gateway:      https://localhost:{AGENTS['api_gateway']['port']}/docs")
        print(f"- Orchestrator API: https://localhost:{AGENTS['orchestrator']['port']}")
        print(f"- Hotel Agent API:  https://localhost:{AGENTS['hotel']['port']}")
        
        print("\nDemo credentials:")
        print("- Username: demo")
        print("- Password: demo123")
        
        print("\nPress Ctrl+C to stop all agents")
        print("="*70 + "\n")
    
    def monitor_agents(self):
        """Monitor agent processes and restart if needed."""
        while self.running:
            try:
                # Check each agent
                for agent_id, config in AGENTS.items():
                    process = self.processes.get(agent_id)
                    
                    if process and process.poll() is not None:
                        # Agent crashed
                        logger.warning(f"{config['name']} stopped unexpectedly. Restarting...")
                        self.processes[agent_id] = self.start_agent(agent_id, config)
                
                # Wait before next check
                time.sleep(5)
                
            except KeyboardInterrupt:
                break
    
    def stop_all_agents(self):
        """Stop all running agents."""
        logger.info("\nStopping all agents...")
        
        # Stop in reverse order (API Gateway first, then orchestrator, then agents)
        for agent_id in reversed(list(AGENTS.keys())):
            process = self.processes.get(agent_id)
            if process and process.poll() is None:
                agent_name = AGENTS[agent_id]["name"]
                logger.info(f"Stopping {agent_name} (PID: {process.pid})")
                
                # Try graceful shutdown first
                process.terminate()
                
                # Wait up to 5 seconds for graceful shutdown
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    logger.warning(f"Force killing {agent_name}")
                    process.kill()
                    process.wait()
        
        logger.info("All agents stopped.")
    
    def run(self):
        """Run the agent launcher."""
        try:
            self.start_all_agents()
            self.monitor_agents()
        except KeyboardInterrupt:
            logger.info("\nShutdown requested...")
        finally:
            self.running = False
            self.stop_all_agents()


def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("SECURE TRAVEL AGENT SYSTEM - A2A LAUNCHER")
    print("="*70)
    print("Security Features: JWT Auth, API Keys, SSL/TLS, Rate Limiting")
    print("="*70 + "\n")
    
    launcher = SecureAgentLauncher()
    
    # Handle signals for clean shutdown
    def signal_handler(sig, frame):
        launcher.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the launcher
    launcher.run()


if __name__ == "__main__":
    main()