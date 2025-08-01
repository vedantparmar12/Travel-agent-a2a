"""
Launch all travel agents as A2A servers.
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


# Agent configuration
AGENTS = {
    "hotel": {
        "name": "Hotel Agent",
        "module": "src.agents.hotel",
        "port": 10010,
        "env_var": "HOTEL_AGENT_PORT"
    },
    "orchestrator": {
        "name": "Orchestrator Agent", 
        "module": "src.agents.orchestrator",
        "port": 10001,
        "env_var": "ORCHESTRATOR_AGENT_PORT",
        "depends_on": ["hotel"]  # Wait for other agents to start first
    }
}


class AgentLauncher:
    """Manages launching and monitoring agent processes."""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = True
    
    def start_agent(self, agent_id: str, config: Dict) -> subprocess.Popen:
        """Start a single agent process."""
        agent_name = config["name"]
        module = config["module"]
        port = os.getenv(config["env_var"], config["port"])
        
        logger.info(f"Starting {agent_name} on port {port}...")
        
        # Set environment variable for port
        env = os.environ.copy()
        env[config["env_var"]] = str(port)
        
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
        time.sleep(2)
        
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
        
        logger.info("\nAll agents started!")
        self.print_status()
    
    def print_status(self):
        """Print the status of all agents."""
        print("\n" + "="*60)
        print("AGENT STATUS")
        print("="*60)
        
        for agent_id, config in AGENTS.items():
            process = self.processes.get(agent_id)
            if process and process.poll() is None:
                port = os.getenv(config["env_var"], config["port"])
                print(f"✓ {config['name']:<20} Running on port {port} (PID: {process.pid})")
            else:
                print(f"✗ {config['name']:<20} Not running")
        
        print("="*60)
        print("\nAccess points:")
        print(f"- Orchestrator API: http://localhost:{AGENTS['orchestrator']['port']}")
        print(f"- Hotel Agent API: http://localhost:{AGENTS['hotel']['port']}")
        print("\nPress Ctrl+C to stop all agents")
        print("="*60 + "\n")
    
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
        
        for agent_id, process in self.processes.items():
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
    print("\n" + "="*60)
    print("TRAVEL AGENT SYSTEM - A2A LAUNCHER")
    print("="*60 + "\n")
    
    launcher = AgentLauncher()
    
    # Handle signals for clean shutdown
    def signal_handler(sig, frame):
        launcher.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the launcher
    launcher.run()


if __name__ == "__main__":
    main()