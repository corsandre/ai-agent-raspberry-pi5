#!/bin/bash
# backup.sh - Backup AI Agent data and configuration

set -e

echo "=========================================="
echo "AI Agent Backup Script"
echo "=========================================="

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="ai-agent-backup-$TIMESTAMP"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_PATH"

echo "📦 Starting backup: $BACKUP_NAME"
echo ""

# 1. Backup Docker Compose configuration
echo "1. 📝 Backing up configuration files..."
mkdir -p "$BACKUP_PATH/config"
cp -r config/* "$BACKUP_PATH/config/" 2>/dev/null || true
cp .env "$BACKUP_PATH/" 2>/dev/null || true
cp docker-compose.yml "$BACKUP_PATH/" 2>/dev/null || true
cp docker-compose.override.yml "$BACKUP_PATH/" 2>/dev/null || true

# 2. Backup source code
echo "2. 💾 Backing up source code..."
mkdir -p "$BACKUP_PATH/src"
cp -r src/* "$BACKUP_PATH/src/" 2>/dev/null || true

# 3. Backup scripts
echo "3. 🔧 Backing up scripts..."
mkdir -p "$BACKUP_PATH/scripts"
cp -r scripts/* "$BACKUP_PATH/scripts/" 2>/dev/null || true

# 4. Backup Docker volumes (if running)
echo "4. 🐳 Backing up Docker volumes..."
if command -v docker &> /dev/null && docker compose ps &> /dev/null; then
    echo "   Docker is running, backing up volumes..."
    
    # Backup workspace
    if docker volume inspect ai-agent_ai-workspace &> /dev/null; then
        echo "   Backing up workspace volume..."
        docker run --rm -v ai-agent_ai-workspace:/data -v "$BACKUP_PATH:/backup" alpine \
            tar czf /backup/workspace.tar.gz -C /data .
    fi
    
    # Backup ChromaDB data
    if docker volume inspect ai-agent_chroma-data &> /dev/null; then
        echo "   Backing up ChromaDB volume..."
        docker run --rm -v ai-agent_chroma-data:/data -v "$BACKUP_PATH:/backup" alpine \
            tar czf /backup/chromadb.tar.gz -C /data .
    fi
    
    # Backup Redis data
    if docker volume inspect ai-agent_redis-data &> /dev/null; then
        echo "   Backing up Redis volume..."
        docker run --rm -v ai-agent_redis-data:/data -v "$BACKUP_PATH:/backup" alpine \
            tar czf /backup/redis.tar.gz -C /data .
    fi
    
    # Backup WebUI data
    if docker volume inspect ai-agent_webui-data &> /dev/null; then
        echo "   Backing up WebUI volume..."
        docker run --rm -v ai-agent_webui-data:/data -v "$BACKUP_PATH:/backup" alpine \
            tar czf /backup/webui.tar.gz -C /data .
    fi
    
    # Get Docker container logs
    echo "   Backing up container logs..."
    docker compose logs --no-color > "$BACKUP_PATH/docker-logs.txt" 2>/dev/null || true
    
    # Get Docker container info
    echo "   Backing up container information..."
    docker ps -a > "$BACKUP_PATH/docker-containers.txt"
    docker images > "$BACKUP_PATH/docker-images.txt"
    docker volume ls > "$BACKUP_PATH/docker-volumes.txt"
    
else
    echo "   Docker not running or no containers found, skipping volume backup"
fi

# 5. Backup host directories
echo "5. 📁 Backing up host directories..."
if [ -d "./data" ]; then
    cp -r ./data "$BACKUP_PATH/" 2>/dev/null || true
fi

if [ -d "./workspace" ]; then
    cp -r ./workspace "$BACKUP_PATH/" 2>/dev/null || true
fi

if [ -d "./logs" ]; then
    cp -r ./logs "$BACKUP_PATH/" 2>/dev/null || true
fi

# 6. Create backup manifest
echo "6. 📋 Creating backup manifest..."
cat > "$BACKUP_PATH/backup-manifest.json" << EOF
{
  "backup_name": "$BACKUP_NAME",
  "timestamp": "$(date -Iseconds)",
  "version": "1.0.0",
  "components": {
    "config": true,
    "source_code": true,
    "scripts": true,
    "docker_volumes": $(command -v docker &> /dev/null && echo "true" || echo "false"),
    "host_directories": true
  },
  "files": [
    $(find "$BACKUP_PATH" -type f -printf '    "%P"\n' | sed '$!s/$/,/')
  ]
}
EOF

# 7. Create restore script
echo "7. 🔄 Creating restore script..."
cat > "$BACKUP_PATH/restore.sh" << 'EOF'
#!/bin/bash
# restore.sh - Restore AI Agent from backup

set -e

echo "=========================================="
echo "AI Agent Restore Script"
echo "=========================================="

# Configuration
BACKUP_DIR=$(dirname "$0")
RESTORE_DIR=".."

if [ ! -f "$BACKUP_DIR/backup-manifest.json" ]; then
    echo "❌ Not a valid backup directory"
    exit 1
fi

echo "📦 Restoring from backup: $(basename "$BACKUP_DIR")"
read -p "Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Restore cancelled"
    exit 1
fi

echo ""

# 1. Restore configuration
echo "1. 📝 Restoring configuration..."
cp -r "$BACKUP_DIR/config" "$RESTORE_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/.env" "$RESTORE_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/docker-compose.yml" "$RESTORE_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/docker-compose.override.yml" "$RESTORE_DIR/" 2>/dev/null || true

# 2. Restore source code
echo "2. 💾 Restoring source code..."
cp -r "$BACKUP_DIR/src" "$RESTORE_DIR/" 2>/dev/null || true

# 3. Restore scripts
echo "3. 🔧 Restoring scripts..."
cp -r "$BACKUP_DIR/scripts" "$RESTORE_DIR/" 2>/dev/null || true

# 4. Restore Docker volumes (if Docker is available)
if command -v docker &> /dev/null; then
    echo "4. 🐳 Restoring Docker volumes..."
    
    # Stop containers if running
    if docker compose ps &> /dev/null; then
        echo "   Stopping containers..."
        docker compose down
    fi
    
    # Restore workspace
    if [ -f "$BACKUP_DIR/workspace.tar.gz" ]; then
        echo "   Restoring workspace volume..."
        docker volume create ai-agent_ai-workspace 2>/dev/null || true
        docker run --rm -v ai-agent_ai-workspace:/data -v "$BACKUP_DIR:/backup" alpine \
            sh -c "cd /data && tar xzf /backup/workspace.tar.gz"
    fi
    
    # Restore ChromaDB
    if [ -f "$BACKUP_DIR/chromadb.tar.gz" ]; then
        echo "   Restoring ChromaDB volume..."
        docker volume create ai-agent_chroma-data 2>/dev/null || true
        docker run --rm -v ai-agent_chroma-data:/data -v "$BACKUP_DIR:/backup" alpine \
            sh -c "cd /data && tar xzf /backup/chromadb.tar.gz"
    fi
    
    # Restore Redis
    if [ -f "$BACKUP_DIR/redis.tar.gz" ]; then
        echo "   Restoring Redis volume..."
        docker volume create ai-agent_redis-data 2>/dev/null || true
        docker run --rm -v ai-agent_redis-data:/data -v "$BACKUP_DIR:/backup" alpine \
            sh -c "cd /data && tar xzf /backup/redis.tar.gz"
    fi
    
    # Restore WebUI
    if [ -f "$BACKUP_DIR/webui.tar.gz" ]; then
        echo "   Restoring WebUI volume..."
        docker volume create ai-agent_webui-data 2>/dev/null || true
        docker run --rm -v ai-agent_webui-data:/data -v "$BACKUP_DIR:/backup" alpine \
            sh -c "cd /data && tar xzf /backup/webui.tar.gz"
    fi
    
else
    echo "4. ⚠️  Docker not found, skipping volume restore"
fi

# 5. Restore host directories
echo "5. 📁 Restoring host directories..."
if [ -d "$BACKUP_DIR/data" ]; then
    cp -r "$BACKUP_DIR/data" "$RESTORE_DIR/" 2>/dev/null || true
fi

if [ -d "$BACKUP_DIR/workspace" ]; then
    cp -r "$BACKUP_DIR/workspace" "$RESTORE_DIR/" 2>/dev/null || true
fi

if [ -d "$BACKUP_DIR/logs" ]; then
    cp -r "$BACKUP_DIR/logs" "$RESTORE_DIR/" 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "✅ Restore complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review configuration files"
echo "2. Update .env with any new API keys"
echo "3. Start services: docker compose up -d"
echo "4. Check logs: docker compose logs -f"
echo ""
EOF

chmod +x "$BACKUP_PATH/restore.sh"

# 8. Create archive
echo "8. 📦 Creating compressed archive..."
cd "$BACKUP_DIR"
tar czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

# 9. Clean old backups (keep last 7)
echo "9. 🧹 Cleaning old backups (keeping last 7)..."
ls -t *.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

# 10. Show backup summary
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)

echo ""
echo "=========================================="
echo "✅ Backup complete!"
echo "=========================================="
echo ""
echo "Backup created: $BACKUP_NAME.tar.gz"
echo "Size: $BACKUP_SIZE"
echo "Location: $BACKUP_DIR/"
echo ""
echo "Contains:"
echo "✓ Configuration files"
echo "✓ Source code"
echo "✓ Scripts"
echo "✓ Docker volumes (if running)"
echo "✓ Host directories"
echo "✓ Restore script"
echo ""
echo "To restore:"
echo "  tar xzf $BACKUP_DIR/$BACKUP_NAME.tar.gz"
echo "  cd $BACKUP_NAME"
echo "  ./restore.sh"
echo ""
echo "Automatic backups can be scheduled with cron:"
echo "  0 2 * * * /path/to/ai-agent/scripts/backup.sh"
echo ""