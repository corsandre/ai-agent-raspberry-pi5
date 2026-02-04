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

`# SSH into your Raspberry Pi 5`
`ssh pi@raspberrypi.local`
``
`# Clone the repository`
`git clone https://github.com/corsandre/ai-agent-raspberry-pi5.git`
`cd ai-agent-raspberry-pi5`
``
`# Make scripts executable`
`chmod +x scripts/*.sh`

### 2. Run Setup Script

`# Run setup script (optimizes Pi 5 and installs Docker)`
`sudo ./scripts/setup_pi5.sh`
``
`# Reboot if prompted`
`sudo reboot`
``
`# SSH back in`
`ssh pi@raspberrypi.local`
`cd ai-agent-raspberry-pi5`

### 3. Configure Environment

`# Copy and edit environment file`
`cp .env.example .env`
`nano .env  # Add your API keys`

**Required in `.env`:**
`KIMI_API_KEY=your_kimi_key_here          # Required for Kimi 2.5k`
`JWT_SECRET_KEY=change_this_random_string # Security`

### 4. Build and Run

`# Build and start all services`
`./build_and_run.sh`
``
`# Or manually:`
`docker compose up -d`

### 5. Verify Installation

`# Check service status`
`docker compose ps`
``
`# Test health endpoint`
`curl http://localhost:3000/health`
``
`# Send your first message`
`curl -X POST http://localhost:3000/chat \`
`  -H "Content-Type: application/json" \`
`  -d '{"message": "Hello, what can you do?"}'`

## 🏗️ Architecture

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

## 📋 Prerequisites

### Hardware Requirements
- **Raspberry Pi 5** (4GB or 8GB recommended)
- **MicroSD card** 32GB+ (Class A1/A2 recommended)
- **Power supply** USB-C PD (5V/3A minimum)
- **Optional**: SSD via PCIe for better performance

### Software Requirements
- **Raspberry Pi OS 64-bit** (Bookworm recommended)
- **Internet connection** for Docker images and API calls
- **API keys** for desired AI providers

## ⚙️ Configuration

### Environment Variables (`.env`)

`# API Keys (required for cloud models)`
`KIMI_API_KEY=your_kimi_key_here`
`# OPENAI_API_KEY=optional_openai_key`
`# CLAUDE_API_KEY=optional_claude_key`
``
`# Docker Settings`
`PUID=1000`
`PGID=1000`
`TZ=UTC`
`WORKSPACE_PATH=/home/pi/ai-workspace`
``
`# Security`
`JWT_SECRET_KEY=change_this_to_a_random_string`
`ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.*,raspberrypi.local`
`MAX_FILE_SIZE_MB=10`
`COMMAND_TIMEOUT_SECONDS=30`
``
`# Resource Limits (adjust for your Pi 5 RAM)`
`MAX_MEMORY_LIMIT=6G  # Leave 2GB for OS on 8GB Pi`
`MAX_CPU_CORES=3      # Leave 1 core for OS`
``
`# LiteLLM Configuration`
`LITELLM_CACHE_SIZE=1000`
`LITELLM_CACHE_TTL=3600`
`LITELLM_PORT=4000`
``
`# Agent Configuration`
`AGENT_HOST=0.0.0.0`
`AGENT_PORT=3000`
`TOOL_SERVER_PORT=5000`
`DEFAULT_MODEL=kimi-2.5k`

### Model Configuration (`config/litellm_config.yaml`)

Configure which models are available:

`model_list:`
`  - model_name: kimi-2.5k`
`    litellm_params:`
`      model: moonshot/moonshot-v1-128k`
`      api_base: https://api.moonshot.cn/v1`
`      api_key: "${KIMI_API_KEY}"`
`  - model_name: local-codellama`
`    litellm_params:`
`      model: ollama/codellama:7b`
`      api_base: http://host.docker.internal:11434`

## 🌐 Services & Ports

| Service | Port | Description | Access |
|---------|------|-------------|--------|
| **AI Agent** | 3000 | Main API server | `http://localhost:3000` |
| **Tool Server** | 5000 | Command execution API | `http://localhost:5000` |
| **LiteLLM Proxy** | 4000 | Model routing layer | `http://localhost:4000` |
| **ChromaDB** | 8000 | Vector database | `http://localhost:8000` |
| **Redis** | 6379 | Caching layer | Internal only |
| **Web UI** | 8080 | Open WebUI interface | `http://localhost:8080` |
| **Grafana** | 3001 | Monitoring dashboard | `http://localhost:3001` |

## 🛠️ Usage

### API Endpoints

#### Health Check
`GET http://localhost:3000/health`

#### Chat with AI
`POST http://localhost:3000/chat`
`Content-Type: application/json`
``
`{`
`  "message": "Write a Python script to list files",`
`  "model": "kimi-2.5k",`
`  "project": "my-project",`
`  "stream": false`
`}`

#### Execute Commands
`POST http://localhost:5000/execute`
`Content-Type: application/json`
``
`{`
`  "command": "ls -la",`
`  "working_dir": "/workspace",`
`  "timeout": 30`
`}`

#### Search Memory
`POST http://localhost:3000/memory/search`
`Content-Type: application/json`
``
`{`
`  "query": "python file operations",`
`  "limit": 5`
`}`

#### List Available Models
`GET http://localhost:3000/models`

#### Switch Default Model
`POST http://localhost:3000/switch-model?model=kimi-2.5k`

### Web Interface

If enabled, access the web UI at `http://raspberrypi.local:8080`

Default credentials:
- Username: `admin`
- Password: `admin` (change on first login)

### Command Line Examples

`# Test the agent`
`curl -X POST http://localhost:3000/chat \`
`  -H "Content-Type: application/json" \`
`  -d '{"message": "List files in workspace"}'`
``
`# Execute a command through the agent`
`curl -X POST http://localhost:3000/chat \`
`  -H "Content-Type: application/json" \`
`  -d '{"message": "Run ls -la in workspace"}'`
``
`# Direct command execution`
`curl -X POST http://localhost:5000/execute \`
`  -H "Content-Type: application/json" \`
`  -d '{"command": "python3 --version"}'`

## 📊 Monitoring

### Basic Monitoring

`# View container logs`
`docker compose logs -f`
``
`# View resource usage`
`docker stats`
``
`# Interactive monitoring dashboard`
`./scripts/monitor.sh`
``
`# System resource monitoring`
`./scripts/monitor.sh --system`
``
`# Service health checks`
`./scripts/monitor.sh --services`

### Cost Tracking

The system automatically tracks API usage costs:

`# View daily cost summary`
`curl http://localhost:3000/cost/daily`
``
`# View monthly forecast`
`curl http://localhost:3000/cost/forecast`
``
`# Get user-specific usage`
`curl http://localhost:3000/cost/user/user123`

### Advanced Monitoring (Optional)

Enable in `docker-compose.yml`:

`# Access Grafana dashboard`
`http://localhost:3001`
``
`# Default credentials`
`Username: admin`
`Password: admin`

## 🔧 Maintenance

### Backup

`# Create complete backup`
`./scripts/backup.sh`
``
`# List available backups`
`ls -la backups/`
``
`# Restore from backup`
`cd backups/`
`tar xzf ai-agent-backup-*.tar.gz`
`cd ai-agent-backup-*/`
`./restore.sh`

### Update

`# Update all services`
`./scripts/update.sh`
``
`# Update Docker images only`
`docker compose pull`
``
`# Rebuild and restart`
`docker compose down`
`docker compose up -d --build`

### Cleanup

`# Remove unused Docker resources`
`docker system prune -f`
``
`# Clean old backups (keeps last 7)`
`./scripts/backup.sh --clean`
``
`# Clear application logs`
`sudo ./scripts/cleanup.sh --logs`

## 🚨 Troubleshooting

### Common Issues

#### 1. Docker Permission Denied
`sudo usermod -aG docker $USER`
`# Log out and back in`
`newgrp docker`

#### 2. Out of Memory on Pi 5
Edit `.env`:
`MAX_MEMORY_LIMIT=4G  # For 4GB Pi 5`
`MAX_MEMORY_LIMIT=6G  # For 8GB Pi 5`

#### 3. Container Won't Start
`# Check logs`
`docker compose logs ai-agent`
``
`# Check Docker daemon`
`sudo systemctl status docker`
``
`# Rebuild from scratch`
`docker compose down -v`
`docker compose up -d --build`

#### 4. API Key Issues
`# Verify .env file`
`cat .env | grep API_KEY`
``
`# Test API connection`
`curl -X POST http://localhost:4000/chat/completions \`
`  -H "Content-Type: application/json" \`
`  -d '{"model": "kimi-2.5k", "messages": [{"role": "user", "content": "test"}]}'`

#### 5. Slow Performance on Pi 5
`# Enable overclocking in setup`
`sudo ./scripts/setup_pi5.sh --overclock`
``
`# Increase swap`
`sudo dphys-swapfile swapoff`
`sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile`
`sudo dphys-swapfile setup`
`sudo dphys-swapfile swapon`

## 📈 Performance on Pi 5 8GB

| Task | Performance | Notes |
|------|------------|-------|
| **Container Startup** | 30-60 seconds | Initial pull takes longer |
| **Chat Response** | 2-5 seconds | Depends on model and network |
| **Command Execution** | < 1 second | Local commands are fast |
| **Memory Usage** | ~3.5GB total | Leaves 4.5GB for OS |
| **Disk Usage** | 2-5GB | Depends on logs and data |
| **Network I/O** | Minimal | Mostly API calls |

## 🔒 Security Features

- **Non-root containers**: All services run as non-root users
- **Command whitelisting**: Only approved commands can be executed
- **Path restrictions**: Cannot access system directories
- **JWT authentication**: Optional API authentication
- **Network isolation**: Services communicate internally
- **Rate limiting**: Prevents API abuse
- **Input validation**: All inputs are sanitized

## 🗂️ Project Structure

ai-agent-raspberry-pi5/
├── docker-compose.yml          # Main Docker configuration
├── docker-compose.override.yml # Development overrides
├── Dockerfile                  # Production build
├── Dockerfile.prod             # Optimized production build
├── Dockerfile.dev              # Development build
├── .env.example               # Environment template
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Development dependencies
├── build_and_run.sh          # Build and start script
├── update.sh                 # Update script
├── backup.sh                 # Backup script
│
├── config/                   # Configuration files
│   ├── litellm_config.yaml   # AI model configuration
│   ├── models.json           # Model definitions
│   ├── chromadb_config.json  # Vector database config
│   ├── agent_config.json     # Agent behavior config
│   └── open-webui.yaml      # Web UI configuration
│
├── src/                      # Python source code
│   ├── docker_main_agent.py  # Main agent application
│   ├── memory_manager.py     # Persistent memory system
│   ├── tool_server.py        # Command execution server
│   ├── system_monitor.py     # System monitoring
│   ├── cost_tracker.py       # API cost tracking
│   └── health_check.py       # Health monitoring
│
├── litellm/                  # LiteLLM proxy service
│   ├── Dockerfile.litellm    # LiteLLM production build
│   ├── Dockerfile.litellm.dev # LiteLLM development build
│   └── requirements_litellm.txt
│
├── monitoring/               # Monitoring configuration
│   ├── dashboards/          # Grafana dashboards
│   └── datasources/         # Prometheus data sources
│
├── scripts/                  # Utility scripts
│   ├── setup_pi5.sh         # Pi 5 optimization
│   ├── install_docker_pi5.sh # Docker installation
│   ├── optimize_docker.sh   # Docker optimization
│   ├── backup.sh           # Backup script
│   ├── update.sh           # Update script
│   ├── migrate.sh          # Database migration
│   ├── monitor.sh          # Monitoring dashboard
│   └── test_agent.sh       # Test suite
│
└── docs/                    # Documentation
    ├── SETUP.md            # Detailed setup guide
    ├── DOCKER_GUIDE.md     # Docker configuration guide
    └── API_REFERENCE.md    # API documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

`# Clone repository`
`git clone https://github.com/corsandre/ai-agent-raspberry-pi5.git`
`cd ai-agent-raspberry-pi5`
``
`# Use development configuration`
`cp docker-compose.override.yml.example docker-compose.override.yml`
``
`# Start development environment`
`docker compose -f docker-compose.yml -f docker-compose.override.yml up -d`

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **LiteLLM** for multi-model proxy support
- **ChromaDB** for vector storage
- **Open WebUI** for the web interface
- **FastAPI** for the API framework
- **Docker** for containerization

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/corsandre/ai-agent-raspberry-pi5/issues)
- **Discussions**: [GitHub Discussions](https://github.com/corsandre/ai-agent-raspberry-pi5/discussions)
- **Wiki**: [Project Wiki](https://github.com/corsandre/ai-agent-raspberry-pi5/wiki)

## 🚧 Roadmap

- [ ] Mobile app interface
- [ ] Voice interaction
- [ ] Plugin system
- [ ] Multi-user support
- [ ] Advanced analytics
- [ ] Backup to cloud storage
- [ ] Automated testing
- [ ] Performance benchmarks

---

**Made with ❤️ for Raspberry Pi 5 enthusiasts**

*If you find this project useful, please give it a ⭐ on GitHub!*