# AI Agent for Raspberry Pi 5 with Docker

A production-ready AI assistant with persistent memory, command line access, and multi-model support (Kimi 2.5k, Claude, OpenAI, local models).

## Features

- **🤖 Multi-Model Support**: Kimi 2.5k, Claude, OpenAI, local Ollama models via LiteLLM
- **🧠 Persistent Memory**: ChromaDB vector storage with conversation history
- **💻 Terminal Access**: Safe command execution with security controls
- **🐳 Dockerized**: Complete Docker Compose setup optimized for Pi 5 ARM64
- **📊 Monitoring**: Built-in health checks and metrics
- **🔄 Easy Switching**: Change AI providers with one config change
- **🔒 Security**: Non-root containers, command whitelisting, network isolation

## Hardware Requirements

- Raspberry Pi 5 (4GB or 8GB recommended)
- MicroSD card 32GB+ (Class A1/A2 recommended)
- Stable power supply (USB-C PD recommended)
- Optional: SSD via PCIe for better performance

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/ai-agent-raspberry-pi5.git
cd ai-agent-raspberry-pi5

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run setup script (optional)
./scripts/setup_pi5.sh

# 4. Start services
docker compose up -d

# 5. Access the agent
curl http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what can you do?"}'


  # AI Agent for Raspberry Pi 5 with Docker

![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi-5-FF0000)
![Docker](https://img.shields.io/badge/Docker-Container-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![AI](https://img.shields.io/badge/AI-Assistant-purple)

A production-ready AI assistant with persistent memory, command line access, and multi-model support (Kimi 2.5k, Claude, OpenAI, local models) running on Raspberry Pi 5.

## ✨ Features

- **🤖 Multi-Model Support**: Kimi 2.5k, Claude, OpenAI, local Ollama models via LiteLLM
- **🧠 Persistent Memory**: ChromaDB vector storage with conversation history
- **💻 Terminal Access**: Safe command execution with security controls
- **🐳 Dockerized**: Complete Docker Compose setup optimized for Pi 5 ARM64
- **📊 Monitoring**: Built-in health checks, system monitoring, and cost tracking
- **🔄 Easy Switching**: Change AI providers with one config change
- **🔒 Security**: Non-root containers, command whitelisting, JWT authentication
- **🌐 Web Interface**: Optional Open WebUI for browser access
- **📈 Cost Tracking**: Real-time API usage cost monitoring
- **🔧 Tool Integration**: File operations, code execution, system management

## 🚀 Quick Start

### 1. Clone & Setup

```bash
# SSH into your Raspberry Pi 5
ssh pi@raspberrypi.local

# Clone the repository
git clone https://github.com/YOUR_USERNAME/ai-agent-raspberry-pi5.git
cd ai-agent-raspberry-pi5

# Make scripts executable
chmod +x scripts/*.sh
```

### 2. Run Setup Script

```bash
# Run setup script (optimizes Pi 5 and installs Docker)
sudo ./scripts/setup_pi5.sh

# Reboot if prompted
sudo reboot

# SSH back in
ssh pi@raspberrypi.local
cd ai-agent-raspberry-pi5
```

### 3. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env
nano .env  # Add your API keys
```

### Required in .env:

```bash
KIMI_API_KEY=your_kimi_key_here          # Required for Kimi 2.5k
JWT_SECRET_KEY=change_this_random_string # Security
```

### 4. Build and Run

```bash
# Build and start all services
./build_and_run.sh

# Or manually:
docker compose up -d
```

### 5. Verify Installation

```bash
# Check service status
docker compose ps

# Test health endpoint
curl http://localhost:3000/health

# Send your first message
curl -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what can you do?"}'
```

### 🏗️ Architecture

```bash
┌─────────────────────────────────────────────────┐
│           Docker Compose Stack                  │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  Redis   │  │ ChromaDB │  │  LiteLLM │     │
│  │  Cache   │  │  Vector  │  │  Proxy   │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│        │             │              │          │
│  ┌─────▼─────────────▼──────────────▼──────┐  │
│  │         Main Agent Container            │  │
│  │  ┌──────────┐  ┌──────────┐            │  │
│  │  │ Tool API │  │ Web API  │            │  │
│  │  │ FastAPI  │  │ FastAPI  │            │  │
│  │  └──────────┘  └──────────┘            │  │
│  └─────────────────────────────────────────┘  │
│        │                     │                 │
│        ▼                     ▼                 │
│  ┌──────────┐        ┌──────────────┐         │
│  │ Host OS  │        │ Volume Mounts│         │
│  │ Commands │        │ ai-workspace │         │
│  └──────────┘        │ chroma-data  │         │
│                      │ logs         │         │
└──────────────────────┴──────────────┴─────────┘
```

📋 Prerequisites
Hardware Requirements
Raspberry Pi 5 (4GB or 8GB recommended)

MicroSD card 32GB+ (Class A1/A2 recommended)

Power supply USB-C PD (5V/3A minimum)

Optional: SSD via PCIe for better performance

Software Requirements
Raspberry Pi OS 64-bit (Bookworm recommended)

Internet connection for Docker images and API calls

API keys for desired AI providers
```

### ⚙️ Configuration

```bash