# Dockerfile
# Multi-stage build for Raspberry Pi 5 ARM64

# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 aiagent

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies as user
USER aiagent
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim-bookworm

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with sudo privileges (for safe command execution)
RUN groupadd -g 1000 aiagent && \
    useradd -m -u 1000 -g aiagent -s /bin/bash aiagent && \
    echo 'aiagent ALL=(ALL) NOPASSWD: /usr/bin/apt, /usr/bin/apt-get, /usr/bin/pip' >> /etc/sudoers.d/aiagent && \
    chmod 0440 /etc/sudoers.d/aiagent

USER aiagent
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder --chown=aiagent:aiagent /home/aiagent/.local /home/aiagent/.local

# Set Python path
ENV PATH="/home/aiagent/.local/bin:${PATH}"
ENV PYTHONPATH="/app"

# Copy application code
COPY --chown=aiagent:aiagent src/ /app/
COPY --chown=aiagent:aiagent config/ /app/config/

# Create necessary directories
RUN mkdir -p /workspace /app/logs && \
    chown aiagent:aiagent /workspace /app/logs

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:3000/health', timeout=2)" || exit 1

# Expose ports
EXPOSE 3000 5000

# Default command
CMD ["python", "docker_main_agent.py"]