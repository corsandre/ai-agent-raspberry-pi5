#!/bin/bash
# optimize_docker.sh - Optimize Docker for AI workloads on Pi 5

set -e

echo "=========================================="
echo "Docker Optimization for Pi 5"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Please run as root: sudo ./optimize_docker.sh"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install it first:"
    echo "   ./scripts/install_docker_pi5.sh"
    exit 1
fi

echo "🔧 Starting Docker optimization..."

# 1. Increase Docker logging limits
echo "📝 Increasing logging limits..."
if [ -f /etc/docker/daemon.json ]; then
    # Backup original
    cp /etc/docker/daemon.json /etc/docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)
fi

cat > /etc/docker/daemon.json << EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
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
  "experimental": false,
  "features": {
    "buildkit": true
  },
  "registry-mirrors": [],
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ],
  "iptables": false,
  "ip-forward": true,
  "ip-masq": true,
  "live-restore": true
}
EOF

# 2. Create Docker systemd service limits
echo "⚙️  Setting systemd limits..."
mkdir -p /etc/systemd/system/docker.service.d/
cat > /etc/systemd/system/docker.service.d/limits.conf << EOF
[Service]
LimitNOFILE=1048576
LimitNPROC=1048576
LimitCORE=infinity
EOF

# 3. Increase system limits for Docker
echo "📁 Increasing system file limits..."
cat > /etc/security/limits.d/docker.conf << EOF
* soft nofile 1048576
* hard nofile 1048576
* soft nproc 1048576
* hard nproc 1048576
EOF

# 4. Configure kernel parameters for Docker
echo "🐧 Configuring kernel parameters..."
cat > /etc/sysctl.d/99-docker-optimize.conf << EOF
# Increase connections
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
net.core.netdev_max_backlog = 5000

# Increase port range
net.ipv4.ip_local_port_range = 10000 65000

# TCP optimization
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15

# Memory optimization
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 60
vm.dirty_background_ratio = 2
vm.max_map_count = 262144

# Network buffer sizes
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
EOF

# Apply sysctl settings
sysctl -p /etc/sysctl.d/99-docker-optimize.conf

# 5. Create Docker cleanup cron job
echo "🧹 Setting up Docker cleanup..."
cat > /etc/cron.daily/docker-cleanup << 'EOF'
#!/bin/bash
# Docker cleanup script
echo "$(date): Running Docker cleanup..."

# Remove stopped containers
docker container prune -f

# Remove dangling images
docker image prune -f

# Remove unused volumes
docker volume prune -f

# Remove unused networks
docker network prune -f

# Remove builder cache
docker builder prune -f

echo "$(date): Docker cleanup complete"
EOF

chmod +x /etc/cron.daily/docker-cleanup

# 6. Enable Docker experimental features (for BuildKit)
echo "🔨 Enabling BuildKit..."
docker version --format '{{.Server.Experimental}}' | grep -q true || {
    echo "Enabling experimental features..."
    systemctl stop docker
    sed -i 's/"experimental": false/"experimental": true/g' /etc/docker/daemon.json
    systemctl start docker
}

# 7. Create Docker health check script
echo "❤️  Creating health check..."
cat > /usr/local/bin/docker-health << 'EOF'
#!/bin/bash
echo "=== Docker Health Check ==="
echo "Time: $(date)"
echo ""
echo "1. Docker Service:"
systemctl is-active docker
echo ""
echo "2. Docker Version:"
docker --version
echo ""
echo "3. Running Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "4. System Resources:"
docker stats --no-stream
echo ""
echo "5. Disk Usage:"
docker system df
EOF

chmod +x /usr/local/bin/docker-health

# 8. Restart Docker
echo "🔄 Restarting Docker..."
systemctl daemon-reload
systemctl restart docker

# 9. Wait for Docker to be ready
echo "⏳ Waiting for Docker to start..."
sleep 5

# 10. Test optimization
echo "🧪 Testing optimization..."
docker run --rm --ulimit nofile=1024:1024 alpine sh -c "ulimit -n"

echo ""
echo "=========================================="
echo "✅ Docker optimization complete!"
echo "=========================================="
echo ""
echo "Optimizations applied:"
echo "✓ Increased logging limits"
echo "✓ Set systemd limits"
echo "✓ Configured kernel parameters"
echo "✓ Added daily cleanup cron job"
echo "✓ Enabled BuildKit (if supported)"
echo "✓ Created health check script"
echo ""
echo "Useful commands:"
echo "  docker-health              # Check Docker status"
echo "  docker stats               # Live container stats"
echo "  docker system prune -a     # Clean everything (careful!)"
echo ""