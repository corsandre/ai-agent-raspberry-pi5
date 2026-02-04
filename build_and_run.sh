#!/bin/bash
# build_and_run.sh - Build and run the AI Agent on Raspberry Pi 5

set -e

echo "=========================================="
echo "AI Agent for Raspberry Pi 5 - Docker Setup"
echo "=========================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This script is optimized for Raspberry Pi 5"
    echo "   It might work on other ARM64 devices, but YMMV"
fi

# Load environment
if [ -f .env ]; then
    echo "📁 Loading environment from .env"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ .env file not found!"
    echo "   Copy .env.example to .env and edit with your API keys"
    exit 1
fi

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker not found. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker installed. Please log out and back in, then run again."
    exit 0
fi

# Check Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo "📦 Docker Compose not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p ./data/redis ./data/chroma ./workspace ./logs ./backups
mkdir -p ./monitoring/dashboards ./monitoring/datasources

# Set permissions
echo "🔒 Setting permissions..."
sudo chown -R $PUID:$PGID ./data ./workspace ./logs 2>/dev/null || true
sudo chmod -R 755 ./data ./workspace ./logs

# Check Pi 5 specific optimizations
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(tr -d '\0' </proc/device-tree/model)
    if [[ $PI_MODEL == *"Raspberry Pi 5"* ]]; then
        echo "🍓 Raspberry Pi 5 detected - applying optimizations..."
        
        # Increase swap for Pi 5
        if [ -f /etc/dphys-swapfile ]; then
            sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
            sudo systemctl restart dphys-swapfile
        fi
        
        # Optimize Docker for Pi 5
        if [ ! -f /etc/docker/daemon.json ]; then
            sudo tee /etc/docker/daemon.json << EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65535,
      "Soft": 65535
    }
  }
}
EOF
            sudo systemctl restart docker
        fi
    fi
fi

# Build Docker images
echo "🔨 Building Docker images..."
docker compose build --progress plain

# Start services
echo "🚀 Starting services..."
docker compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start (30 seconds)..."
sleep 30

# Check service status
echo "📊 Service status:"
docker compose ps

# Show exposed ports
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Access points:"
echo "   Main Agent API:    http://${LOCAL_IP}:3000"
echo "   Tool Server:       http://${LOCAL_IP}:5000"
echo "   LiteLLM Proxy:     http://${LOCAL_IP}:4000"
echo "   Web UI (optional): http://${LOCAL_IP}:8080"
echo "   Grafana:           http://${LOCAL_IP}:3001"
echo ""
echo "📝 Test the agent:"
echo "   curl -X POST http://${LOCAL_IP}:3000/chat \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"message\": \"Hello, what can you do?\"}'"
echo ""
echo "📋 View logs:"
echo "   docker compose logs -f ai-agent"
echo ""
echo "🛑 To stop services:"
echo "   docker compose down"