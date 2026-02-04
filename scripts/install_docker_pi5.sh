#!/bin/bash
# install_docker_pi5.sh - Install Docker and dependencies on Raspberry Pi 5

set -e

echo "=========================================="
echo "Docker Installation for Raspberry Pi 5"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Please run as root: sudo ./install_docker_pi5.sh"
    exit 1
fi

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "❌ This script is for ARM64 (aarch64) only. Detected: $ARCH"
    echo "   Raspberry Pi 5 should be aarch64. Check your OS."
    exit 1
fi

echo "📱 Architecture: $ARCH"
echo "🍓 Raspberry Pi 5 detected"

# Update system
echo "🔄 Updating system packages..."
apt-get update
apt-get upgrade -y

# Install prerequisites
echo "📦 Installing prerequisites..."
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    python3-pip \
    python3-venv \
    git \
    htop \
    iotop \
    iftop \
    net-tools

# Remove old Docker if exists
echo "🧹 Removing old Docker versions..."
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Add Docker's official GPG key
echo "🔑 Adding Docker GPG key..."
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up repository
echo "📚 Setting up Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update again
apt-get update

# Install Docker
echo "🐳 Installing Docker Engine..."
apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# Add user to docker group
echo "👥 Adding current user to docker group..."
usermod -aG docker $SUDO_USER

# Configure Docker for Pi 5
echo "⚙️  Configuring Docker for Pi 5..."
cat > /etc/docker/daemon.json << EOF
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
  },
  "exec-opts": ["native.cgroupdriver=systemd"],
  "data-root": "/var/lib/docker",
  "experimental": false,
  "features": {
    "buildkit": true
  },
  "registry-mirrors": []
}
EOF

# Enable cgroups
echo "📦 Enabling cgroups..."
if ! grep -q "cgroup" /boot/cmdline.txt; then
    echo "cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1 swapaccount=1" >> /boot/cmdline.txt
fi

# Restart Docker
echo "🔄 Restarting Docker..."
systemctl restart docker
systemctl enable docker

# Install Docker Compose if not installed via plugin
if ! command -v docker compose &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    pip3 install docker-compose
fi

# Verify installation
echo "✅ Verifying Docker installation..."
docker --version
docker compose version

# Test Docker
echo "🧪 Testing Docker with hello-world..."
docker run --rm hello-world

echo ""
echo "=========================================="
echo "✅ Docker installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Log out and back in for group changes to take effect"
echo "2. Test with: docker run hello-world"
echo "3. Clone AI Agent repository"
echo ""
echo "Or run the complete setup:"
echo "  ./scripts/setup_pi5.sh"