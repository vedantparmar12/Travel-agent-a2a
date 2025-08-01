# Multi-stage Dockerfile for Travel Agent System

# Stage 1: Base image with Python
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Development image
FROM base as development

# Install development dependencies
RUN pip install --no-cache-dir \
    ipython \
    ipdb \
    pre-commit

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command for development
CMD ["python", "-m", "src.launch_agents"]

# Stage 3: Production image for individual agents
FROM base as agent-base

# Create non-root user
RUN useradd -m -u 1000 agent && \
    chown -R agent:agent /app

# Copy only necessary files
COPY --chown=agent:agent src/ /app/src/
COPY --chown=agent:agent setup.py /app/
COPY --chown=agent:agent README.md /app/

# Switch to non-root user
USER agent

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Stage 4: Specific agent images
FROM agent-base as hotel-agent
ENV SERVICE_NAME=hotel
CMD ["python", "-m", "src.agents.hotel"]

FROM agent-base as transport-agent
ENV SERVICE_NAME=transport
CMD ["python", "-m", "src.agents.transport"]

FROM agent-base as activity-agent
ENV SERVICE_NAME=activity
CMD ["python", "-m", "src.agents.activity"]

FROM agent-base as budget-agent
ENV SERVICE_NAME=budget
CMD ["python", "-m", "src.agents.budget"]

FROM agent-base as itinerary-agent
ENV SERVICE_NAME=itinerary
CMD ["python", "-m", "src.agents.itinerary"]

FROM agent-base as orchestrator-agent
ENV SERVICE_NAME=orchestrator
CMD ["python", "-m", "src.agents.orchestrator"]

# Stage 5: API Gateway / Client
FROM agent-base as client
COPY --chown=agent:agent src/travel_client.py /app/src/
CMD ["python", "src/travel_client.py"]