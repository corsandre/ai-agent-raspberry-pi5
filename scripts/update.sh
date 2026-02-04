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

# Backup before update
echo -e "${YELLOW}⚠️  Creating backup before update...${NC}"
./scripts/backup.sh

# Stop services
echo -e "${YELLOW}🛑 Stopping services...${NC}"
docker compose down

# Pull latest images
echo -e "${YELLOW}📥 Pulling latest Docker images...${NC}"
docker compose pull

# Rebuild with no cache
echo -e "${YELLOW}🔨 Rebuilding containers...${NC}"
docker compose build --no-cache --progress plain

# Migrate database if needed
echo -e "${YELLOW}🔄 Checking for migrations...${NC}"
if [ -f "scripts/migrate.sh" ]; then
    ./scripts/migrate.sh
fi

# Start services
echo -e "${YELLOW}🚀 Starting services...${NC}"
docker compose up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 30

# Check service status
echo -e "${YELLOW}📊 Checking service status...${NC}"
docker compose ps

# Run health checks
echo -e "${YELLOW}❤️  Running health checks...${NC}"
if curl -s http://localhost:3000/health > /dev/null; then
    echo -e "${GREEN}✅ Main agent is healthy${NC}"
else
    echo -e "${RED}❌ Main agent health check failed${NC}"
fi

if curl -s http://localhost:4000/health > /dev/null; then
    echo -e "${GREEN}✅ LiteLLM proxy is healthy${NC}"
else
    echo -e "${RED}❌ LiteLLM proxy health check failed${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ Update complete!${NC}"
echo "=========================================="
echo ""
echo "Services updated:"
echo "✓ AI Agent"
echo "✓ LiteLLM Proxy"
echo "✓ ChromaDB"
echo "✓ Redis"
echo "✓ Web UI (if enabled)"
echo ""
echo "To view logs:"
echo "  docker compose logs -f"
echo ""
echo "To rollback (if needed):"
echo "  1. Go to backups/ directory"
echo "  2. Extract latest backup"
echo "  3. Run restore.sh"
echo ""