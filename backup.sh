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

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to create backup directory
create_backup_dir() {
    echo -e "${YELLOW}📁 Creating backup directory...${NC}"
    mkdir -p "$BACKUP_PATH"
    mkdir -p "$BACKUP_PATH/config"
    mkdir -p "$BACKUP_PATH/src"
    mkdir -p "$BACKUP_PATH/scripts"
    mkdir -p "$BACKUP_PATH/docker"
}

# Function to backup configuration
backup_config() {
    echo -e "${YELLOW}1. 📝 Backing up configuration files...${NC}"
    
    # Core configuration
    cp -r config/* "$BACKUP_PATH/config/" 2>/dev/null || echo -e "${RED}⚠️  No config directory${NC}"
    
    # Docker files
    cp .env "$BACKUP_PATH/" 2>/dev/null || echo -e "${RED}⚠️  No .env file${NC}"
    cp docker-compose.yml "$BACKUP_PATH/" 2>/dev/null || echo -e "${RED}⚠️  No docker-compose.yml${NC}"
    cp docker-compose.override.yml "$BACKUP_PATH/" 2>/dev/null || true
    cp Dockerfile "$BACKUP_PATH/" 2>/dev/null || true
    cp Dockerfile.prod "$BACKUP_PATH/" 2>/dev/null || true
    cp requirements.txt "$BACKUP_PATH/" 2>/dev/null || true
    
    # Scripts
    cp -r scripts/* "$BACKUP_PATH/scripts/" 2>/dev/null || echo -e "${RED}⚠️  No scripts directory${NC}"
    
    # Source code
    cp -r src/* "$BACKUP_PATH/src/" 2>/dev/null || echo -e "${RED}⚠️  No src directory${NC}"
}

# Function to backup Docker volumes
backup_docker_volumes() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found, skipping volume backup${NC}"
        return
    fi
    
    echo -e "${YELLOW}2. 🐳 Backing up Docker volumes...${NC}"
    
    # List of volumes to backup
    VOLUMES=(
        "ai-agent_ai-workspace"
        "ai-agent_chroma-data"
        "ai-agent_redis-data"
        "ai-agent_webui-data"
        "ai-agent_prometheus-data"
        "ai-agent_grafana-data"
    )
    
    for volume in "${VOLUMES[@]}"; do
        if docker volume inspect "$volume" &> /dev/null; then
            echo -e "   Backing up volume: $volume"
            docker run --rm \
                -v "$volume:/data:ro" \
                -v "$BACKUP_PATH:/backup" \
                alpine \
                tar czf "/backup/${volume}.tar.gz" -C /data . 2>/dev/null || true
        fi
    done
    
    # Backup Docker container info
    echo -e "   Backing up Docker information..."
    docker ps -a > "$BACKUP_PATH/docker-containers.txt" 2>/dev/null || true
    docker images > "$BACKUP_PATH/docker-images.txt" 2>/dev/null || true
    docker volume ls > "$BACKUP_PATH/docker-volumes.txt" 2>/dev/null || true
    docker network ls > "$BACKUP_PATH/docker-networks.txt" 2>/dev/null || true
    
    # Backup Docker logs if containers are running
    if docker compose ps &> /dev/null; then
        docker compose logs --no-color > "$BACKUP_PATH/docker-logs.txt" 2>/dev/null || true
    fi
}

# Function to backup host directories
backup_host_directories() {
    echo -e "${YELLOW}3. 📁 Backing up host directories...${NC}"
    
    # Backup local data directories
    if [ -d "./data" ]; then
        echo -e "   Backing up ./data"
        cp -r ./data "$BACKUP_PATH/" 2>/dev/null || true
    fi
    
    if [ -d "./workspace" ]; then
        echo -e "   Backing up ./workspace"
        cp -r ./workspace "$BACKUP_PATH/" 2>/dev/null || true
    fi
    
    if [ -d "./logs" ]; then
        echo -e "   Backing up ./logs"
        cp -r ./logs "$BACKUP_PATH/" 2>/dev/null || true
    fi
    
    if [ -d "./monitoring" ]; then
        echo -e "   Backing up ./monitoring"
        cp -r ./monitoring "$BACKUP_PATH/" 2>/dev/null || true
    fi
}

# Function to create backup manifest
create_manifest() {
    echo -e "${YELLOW}4. 📋 Creating backup manifest...${NC}"
    
    cat > "$BACKUP_PATH/backup-manifest.json" << EOF
{
  "backup_name": "$BACKUP_NAME",
  "timestamp": "$(date -Iseconds)",
  "system": "$(uname -a)",
  "ai_agent_version": "1.0.0",
  "docker_version": "$(docker --version 2>/dev/null || echo "not installed")",
  "components": {
    "config": $(if [ -d "$BACKUP_PATH/config" ]; then echo "true"; else echo "false"; fi),
    "source_code": $(if [ -d "$BACKUP_PATH/src" ]; then echo "true"; else echo "false"; fi),
    "scripts": $(if [ -d "$BACKUP_PATH/scripts" ]; then echo "true"; else echo "false"; fi),
    "docker_volumes": $(ls "$BACKUP_PATH"/*.tar.gz 2>/dev/null | wc -l),
    "host_directories": $(if [ -d "$BACKUP_PATH/data" ] || [ -d "$BACKUP_PATH/workspace" ] || [ -d "$BACKUP_PATH/logs" ]; then echo "true"; else echo "false"; fi)
  },
  "file_count": $(find "$BACKUP_PATH" -type f | wc -l),
  "total_size_bytes": $(du -sb "$BACKUP_PATH" | cut -f1)
}
EOF
}

# Function to create restore script
create_restore_script() {
    echo -e "${YELLOW}5. 🔄 Creating restore script...${NC}"
    
    cat > "$BACKUP_PATH/restore.sh" << 'EOF'
#!/bin/bash
# restore.sh - Restore AI Agent from backup

set -e

echo "=========================================="
echo "AI Agent Restore Script"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BACKUP_DIR=$(cd "$(dirname "$0")" && pwd)
RESTORE_DIR=$(cd "$BACKUP_DIR/.." && pwd)

# Check if this is a valid backup
if [ ! -f "$BACKUP_DIR/backup-manifest.json" ]; then
    echo -e "${RED}❌ Not a valid backup directory${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Restoring from backup: $(basename "$BACKUP_DIR")${NC}"
echo -e "${YELLOW}📁 Restore target: $RESTORE_DIR${NC}"

# Confirm restore
read -p "Are you sure you want to restore? This will overwrite existing files. (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Restore cancelled${NC}"
    exit 1
fi

echo ""

# 1. Restore configuration
echo -e "${YELLOW}1. 📝 Restoring configuration...${NC}"
if [ -d "$BACKUP_DIR/config" ]; then
    cp -r "$BACKUP_DIR/config" "$RESTORE_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✅ Configuration restored${NC}"
else
    echo -e "${RED}⚠️  No config directory in backup${NC}"
fi

if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" "$RESTORE_DIR/" 2>/dev/null || true
fi

if [ -f "$BACKUP_DIR/docker-compose.yml" ]; then
    cp "$BACKUP_DIR/docker-compose.yml" "$RESTORE_DIR/" 2>/dev/null || true
fi

if [ -f "$BACKUP_DIR/docker-compose.override.yml" ]; then
    cp "$BACKUP_DIR/docker-compose.override.yml" "$RESTORE_DIR/" 2>/dev/null || true
fi

# 2. Restore source code
echo -e "${YELLOW}2. 💾 Restoring source code...${NC}"
if [ -d "$BACKUP_DIR/src" ]; then
    cp -r "$BACKUP_DIR/src" "$RESTORE_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✅ Source code restored${NC}"
else
    echo -e "${RED}⚠️  No source code in backup${NC}"
fi

# 3. Restore scripts
echo -e "${YELLOW}3. 🔧 Restoring scripts...${NC}"
if [ -d "$BACKUP_DIR/scripts" ]; then
    cp -r "$BACKUP_DIR/scripts" "$RESTORE_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✅ Scripts restored${NC}"
else
    echo -e "${RED}⚠️  No scripts in backup${NC}"
fi

# 4. Restore Docker volumes
if command -v docker &> /dev/null; then
    echo -e "${YELLOW}4. 🐳 Restoring Docker volumes...${NC}"
    
    # Stop containers if running
    if docker compose ps &> /dev/null; then
        echo -e "   Stopping containers..."
        docker compose down
    fi
    
    # Restore each volume
    for volume_file in "$BACKUP_DIR"/*.tar.gz; do
        if [ -f "$volume_file" ]; then
            volume_name=$(basename "$volume_file" .tar.gz)
            echo -e "   Restoring volume: $volume_name"
            
            # Remove existing volume
            docker volume rm "$volume_name" 2>/dev/null || true
            
            # Create new volume
            docker volume create "$volume_name" 2>/dev/null || true
            
            # Restore data
            docker run --rm \
                -v "$volume_name:/data" \
                -v "$volume_file:/backup.tar.gz:ro" \
                alpine \
                sh -c "cd /data && tar xzf /backup.tar.gz" 2>/dev/null || true
        fi
    done
else
    echo -e "${RED}4. ⚠️  Docker not found, skipping volume restore${NC}"
fi

# 5. Restore host directories
echo -e "${YELLOW}5. 📁 Restoring host directories...${NC}"
if [ -d "$BACKUP_DIR/data" ]; then
    cp -r "$BACKUP_DIR/data" "$RESTORE_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✅ Host data restored${NC}"
fi

if [ -d "$BACKUP_DIR/workspace" ]; then
    cp -r "$BACKUP_DIR/workspace" "$RESTORE_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✅ Workspace restored${NC}"
fi

if [ -d "$BACKUP_DIR/logs" ]; then
    cp -r "$BACKUP_DIR/logs" "$RESTORE_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✅ Logs restored${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ Restore complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review configuration files"
echo "2. Update .env with any API keys if needed"
echo "3. Start services: docker compose up -d"
echo "4. Check logs: docker compose logs -f"
echo ""
EOF

    chmod +x "$BACKUP_PATH/restore.sh"
    echo -e "${GREEN}✅ Restore script created${NC}"
}

# Function to create archive
create_archive() {
    echo -e "${YELLOW}6. 📦 Creating compressed archive...${NC}"
    cd "$BACKUP_DIR"
    tar czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME" 2>/dev/null || {
        echo -e "${RED}❌ Failed to create archive${NC}"
        return 1
    }
    
    # Remove uncompressed backup
    rm -rf "$BACKUP_NAME"
    
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)
    echo -e "${GREEN}✅ Archive created: $BACKUP_NAME.tar.gz ($BACKUP_SIZE)${NC}"
}

# Function to clean old backups
clean_old_backups() {
    echo -e "${YELLOW}7. 🧹 Cleaning old backups (keeping last 7)...${NC}"
    cd "$BACKUP_DIR"
    ls -t *.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
    echo -e "${GREEN}✅ Old backups cleaned${NC}"
}

# Function to show backup summary
show_summary() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}✅ Backup complete!${NC}"
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
    echo "✓ Docker volumes (if Docker was running)"
    echo "✓ Host directories"
    echo "✓ Restore script"
    echo ""
    echo "To restore:"
    echo "  cd $BACKUP_DIR"
    echo "  tar xzf $BACKUP_NAME.tar.gz"
    echo "  cd $BACKUP_NAME"
    echo "  ./restore.sh"
    echo ""
    echo "To schedule automatic backups with cron:"
    echo "  0 2 * * * cd /path/to/ai-agent && ./backup.sh"
    echo ""
}

# Main backup process
main() {
    create_backup_dir
    backup_config
    backup_docker_volumes
    backup_host_directories
    create_manifest
    create_restore_script
    create_archive
    clean_old_backups
    show_summary
}

# Run main function
main "$@"