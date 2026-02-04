#!/bin/bash
# update.sh - Update AI Agent to latest version

set -e

echo "=========================================="
echo "AI Agent Update Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}⚠️  Some operations require root. You may be prompted for sudo password.${NC}"
    fi
}

# Function to backup before update
backup() {
    echo -e "${YELLOW}📦 Creating backup before update...${NC}"
    if [ -f "./scripts/backup.sh" ]; then
        ./scripts/backup.sh
    else
        echo -e "${RED}❌ Backup script not found${NC}"
        read -p "Continue without backup? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to stop services
stop_services() {
    echo -e "${YELLOW}🛑 Stopping services...${NC}"
    if command -v docker-compose &> /dev/null || command -v docker compose &> /dev/null; then
        docker compose down
        sleep 3
    else
        echo -e "${RED}❌ Docker Compose not found${NC}"
        exit 1
    fi
}

# Function to pull updates
pull_updates() {
    echo -e "${YELLOW}📥 Pulling latest Docker images...${NC}"
    docker compose pull
    
    echo -e "${YELLOW}🔨 Rebuilding containers...${NC}"
    docker compose build --no-cache --progress plain
}

# Function to migrate data
migrate_data() {
    echo -e "${YELLOW}🔄 Checking for migrations...${NC}"
    if [ -f "./scripts/migrate.sh" ]; then
        ./scripts/migrate.sh
    else
        echo -e "${YELLOW}⚠️  No migration script found, skipping...${NC}"
    fi
}

# Function to start services
start_services() {
    echo -e "${YELLOW}🚀 Starting services...${NC}"
    docker compose up -d
    
    echo -e "${YELLOW}⏳ Waiting for services to start (30 seconds)...${NC}"
    sleep 30
}

# Function to check service status
check_status() {
    echo -e "${YELLOW}📊 Checking service status...${NC}"
    docker compose ps
    
    echo -e "${YELLOW}❤️  Running health checks...${NC}"
    
    # Check main agent
    if curl -s --max-time 5 http://localhost:3000/health > /dev/null; then
        echo -e "${GREEN}✅ Main agent is healthy${NC}"
    else
        echo -e "${RED}❌ Main agent health check failed${NC}"
        echo -e "${YELLOW}Showing logs...${NC}"
        docker compose logs ai-agent --tail=20
    fi
    
    # Check LiteLLM
    if curl -s --max-time 5 http://localhost:4000/health > /dev/null; then
        echo -e "${GREEN}✅ LiteLLM proxy is healthy${NC}"
    else
        echo -e "${RED}❌ LiteLLM proxy health check failed${NC}"
    fi
    
    # Check ChromaDB
    if curl -s --max-time 5 http://localhost:8000/api/v1/heartbeat > /dev/null; then
        echo -e "${GREEN}✅ ChromaDB is healthy${NC}"
    else
        echo -e "${RED}❌ ChromaDB health check failed${NC}"
    fi
    
    # Check Redis
    if docker exec ai-agent-redis redis-cli ping 2>/dev/null | grep -q PONG; then
        echo -e "${GREEN}✅ Redis is healthy${NC}"
    else
        echo -e "${RED}❌ Redis health check failed${NC}"
    fi
}

# Function to clean up
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up unused Docker resources...${NC}"
    docker system prune -f
}

# Function to show update summary
show_summary() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}✅ Update complete!${NC}"
    echo "=========================================="
    echo ""
    echo "Services updated:"
    echo "✓ AI Agent (http://localhost:3000)"
    echo "✓ LiteLLM Proxy (http://localhost:4000)"
    echo "✓ ChromaDB Vector Store (http://localhost:8000)"
    echo "✓ Redis Cache (localhost:6379)"
    echo "✓ Web UI (http://localhost:8080) - if enabled"
    echo ""
    echo "Useful commands:"
    echo "  docker compose logs -f           # View all logs"
    echo "  docker compose logs ai-agent    # View agent logs"
    echo "  docker stats                    # View resource usage"
    echo ""
    echo "To test the update:"
    echo "  curl http://localhost:3000/health"
    echo "  curl -X POST http://localhost:3000/chat \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"message\": \"Hello, are you updated?\"}'"
    echo ""
    echo "=========================================="
}

# Main update process
main() {
    check_root
    backup
    stop_services
    pull_updates
    migrate_data
    start_services
    check_status
    cleanup
    show_summary
}

# Run main function
main "$@"