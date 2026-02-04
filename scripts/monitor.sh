#!/bin/bash
# monitor.sh - Monitor AI Agent services and resources

set -e

echo "=========================================="
echo "AI Agent Monitor"
echo "=========================================="

while true; do
    clear
    
    echo "$(date)"
    echo "=========================================="
    echo "           AI Agent Dashboard"
    echo "=========================================="
    
    # 1. System Resources
    echo ""
    echo "1. 📊 SYSTEM RESOURCES"
    echo "----------------------"
    echo "CPU:  $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
    echo "RAM:  $(free -m | awk '/^Mem:/{printf "%.1f%% (%dMB/%dMB)\n", $3/$2*100, $3, $2}')"
    echo "Disk: $(df -h / | awk 'NR==2{print $5 " (" $3 "/" $2 ")"}')"
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "0")
    echo "Temp: $((TEMP/1000))°C"
    
    # 2. Docker Status
    echo ""
    echo "2. 🐳 DOCKER STATUS"
    echo "------------------"
    if command -v docker &> /dev/null; then
        RUNNING=$(docker ps -q | wc -l)
        TOTAL=$(docker ps -a -q | wc -l)
        echo "Containers: $RUNNING running, $TOTAL total"
        
        # Show container status
        echo ""
        echo "Containers:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -10
    else
        echo "Docker not installed"
    fi
    
    # 3. AI Agent Services
    echo ""
    echo "3. 🤖 AI AGENT SERVICES"
    echo "----------------------"
    
    # Check main agent
    if curl -s --max-time 2 http://localhost:3000/health > /dev/null; then
        echo "Main Agent:    ✅ Online"
    else
        echo "Main Agent:    ❌ Offline"
    fi
    
    # Check LiteLLM
    if curl -s --max-time 2 http://localhost:4000/health > /dev/null; then
        echo "LiteLLM Proxy: ✅ Online"
    else
        echo "LiteLLM Proxy: ❌ Offline"
    fi
    
    # Check ChromaDB
    if curl -s --max-time 2 http://localhost:8000/api/v1/heartbeat > /dev/null; then
        echo "ChromaDB:      ✅ Online"
    else
        echo "ChromaDB:      ❌ Offline"
    fi
    
    # Check Redis
    if docker exec ai-agent-redis redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "Redis:         ✅ Online"
    else
        echo "Redis:         ❌ Offline"
    fi
    
    # 4. Recent Logs
    echo ""
    echo "4. 📝 RECENT LOGS (last 5 lines)"
    echo "-------------------------------"
    if [ -f "logs/agent.log" ]; then
        tail -5 logs/agent.log
    else
        echo "No logs found"
    fi
    
    # 5. API Status
    echo ""
    echo "5. 🔌 API ENDPOINTS"
    echo "------------------"
    echo "Agent API:    http://localhost:3000"
    echo "Tool Server:  http://localhost:5000"
    echo "LiteLLM:      http://localhost:4000"
    echo "Web UI:       http://localhost:8080"
    echo "Grafana:      http://localhost:3001"
    
    # 6. Actions
    echo ""
    echo "=========================================="
    echo "ACTIONS:"
    echo "  r) Refresh      l) View Logs"
    echo "  s) Start        t) Stop"
    echo "  b) Backup       u) Update"
    echo "  q) Quit"
    echo "=========================================="
    
    # Read input
    read -t 10 -n 1 -p "Select action (r/l/s/t/b/u/q): " choice
    echo ""
    
    case $choice in
        r|"")
            # Refresh (default)
            continue
            ;;
        l)
            echo "Showing logs... (Ctrl+C to return)"
            docker compose logs -f --tail=50
            read -p "Press Enter to continue..."
            ;;
        s)
            echo "Starting services..."
            docker compose up -d
            sleep 5
            ;;
        t)
            echo "Stopping services..."
            docker compose down
            sleep 2
            ;;
        b)
            echo "Creating backup..."
            ./scripts/backup.sh
            read -p "Press Enter to continue..."
            ;;
        u)
            echo "Updating..."
            ./scripts/update.sh
            read -p "Press Enter to continue..."
            ;;
        q)
            echo "Exiting monitor..."
            exit 0
            ;;
        *)
            echo "Invalid choice"
            sleep 1
            ;;
    esac
done