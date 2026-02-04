#!/bin/bash
# setup_pi5.sh - Optimize Raspberry Pi 5 for Docker and AI workloads

set -e

echo "=========================================="
echo "Raspberry Pi 5 Optimization Script"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Please run as root: sudo ./setup_pi5.sh"
    exit 1
fi

# Detect Pi 5
PI_MODEL=$(tr -d '\0' </proc/device-tree/model 2>/dev/null || echo "Unknown")
echo "📱 Detected: $PI_MODEL"

if [[ ! $PI_MODEL == *"Raspberry Pi 5"* ]]; then
    echo "❌ This script is for Raspberry Pi 5 only!"
    exit 1
fi

echo "🔧 Starting optimization..."

# 1. Update system
echo "🔄 Updating system..."
apt-get update
apt-get upgrade -y

# 2. Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $SUDO_USER
fi

# 3. Install Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    apt-get install -y docker-compose-plugin
fi

# 4. Increase swap for Pi 5 (8GB models can use less)
echo "💾 Configuring swap..."
if [ -f /etc/dphys-swapfile ]; then
    TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
    
    if [ $TOTAL_MEM -lt 4096 ]; then
        # 4GB or less: 2GB swap
        SWAP_SIZE=2048
    elif [ $TOTAL_MEM -lt 8192 ]; then
        # 4-8GB: 4GB swap
        SWAP_SIZE=4096
    else
        # 8GB+: 2GB swap (shouldn't need much)
        SWAP_SIZE=2048
    fi
    
    sed -i "s/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=$SWAP_SIZE/" /etc/dphys-swapfile
    systemctl restart dphys-swapfile
    echo "✅ Swap set to ${SWAP_SIZE}MB"
fi

# 5. Overclock Pi 5 (optional but recommended)
echo "⚡ Configuring overclock..."
if ! grep -q "overclock" /boot/config.txt; then
    cat >> /boot/config.txt << EOF

# Pi 5 Overclock for AI workloads
over_voltage=6
arm_freq=2800
gpu_freq=850
EOF
    echo "✅ Overclock configured (2.8GHz CPU, 850MHz GPU)"
fi

# 6. Configure Docker for Pi 5
echo "🐳 Optimizing Docker..."
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
  "experimental": false,
  "features": {
    "buildkit": true
  }
}
EOF

systemctl restart docker

# 7. Install monitoring tools
echo "📊 Installing monitoring tools..."
apt-get install -y htop iotop iftop nmon

# 8. Disable unnecessary services
echo "🛑 Disabling unnecessary services..."
systemctl disable bluetooth 2>/dev/null || true
systemctl disable avahi-daemon 2>/dev/null || true
systemctl disable triggerhappy 2>/dev/null || true

# 9. Set performance governor
echo "🎛️  Setting CPU governor to performance..."
if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    echo "performance" | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
fi

# 10. Increase file limits
echo "📁 Increasing file limits..."
cat > /etc/security/limits.d/99-ai-agent.conf << EOF
* soft nofile 65535
* hard nofile 65535
* soft nproc 65535
* hard nproc 65535
EOF

# 11. Configure sysctl for better performance
echo "⚙️  Configuring kernel parameters..."
cat > /etc/sysctl.d/99-ai-agent.conf << EOF
# Network
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
net.core.somaxconn = 1024
net.core.netdev_max_backlog = 5000

# Virtual memory
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 60
vm.dirty_background_ratio = 2

# Inotify (for file watching)
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 512
EOF

sysctl -p /etc/sysctl.d/99-ai-agent.conf

# 12. Enable cgroups for Docker
echo "📦 Enabling cgroups..."
if ! grep -q "cgroup" /boot/cmdline.txt; then
    sed -i 's/$/ cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1 swapaccount=1/' /boot/cmdline.txt
fi

# 13. Create AI workspace
echo "📂 Creating workspace directory..."
mkdir -p /home/$SUDO_USER/ai-workspace
chown -R $SUDO_USER:$SUDO_USER /home/$SUDO_USER/ai-workspace

# 14. Install Python 3.11 if not present
if ! command -v python3.11 &> /dev/null; then
    echo "🐍 Installing Python 3.11..."
    apt-get install -y python3.11 python3.11-venv python3.11-dev
fi

echo ""
echo "=========================================="
echo "✅ Optimization complete!"
echo "=========================================="
echo ""
echo "Recommended next steps:"
echo "1. Reboot: sudo reboot"
echo "2. Clone AI Agent repository"
echo "3. Configure .env file with API keys"
echo "4. Run: ./build_and_run.sh"
echo ""
echo "To monitor performance:"
echo "  htop          # CPU/Memory"
echo "  iotop -o      # Disk I/O"
echo "  iftop         # Network"
echo "  docker stats  # Container resources"
echo ""