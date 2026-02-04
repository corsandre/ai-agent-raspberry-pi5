#!/bin/bash
# test_agent.sh - Test AI Agent functionality

set -e

echo "=========================================="
echo "AI Agent Test Suite"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test 1: Health Check
echo -e "${YELLOW}1. Testing health check...${NC}"
if curl -s http://localhost:3000/health > /dev/null; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    exit 1
fi

# Test 2: Chat endpoint
echo -e "${YELLOW}2. Testing chat endpoint...${NC}"
RESPONSE=$(curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, are you working?", "stream": false}' | jq -r '.response' 2>/dev/null || echo "ERROR")

if [ "$RESPONSE" != "ERROR" ] && [ ! -z "$RESPONSE" ]; then
    echo -e "${GREEN}✅ Chat endpoint working${NC}"
    echo "   Response: ${RESPONSE:0:100}..."
else
    echo -e "${RED}❌ Chat endpoint failed${NC}"
fi

# Test 3: Tool execution
echo -e "${YELLOW}3. Testing tool execution...${NC}"
RESULT=$(curl -s -X POST http://localhost:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "pwd", "working_dir": "/workspace"}' | jq -r '.success' 2>/dev/null || echo "false")

if [ "$RESULT" = "true" ]; then
    echo -e "${GREEN}✅ Tool execution working${NC}"
else
    echo -e "${RED}❌ Tool execution failed${NC}"
fi

# Test 4: Memory search
echo -e "${YELLOW}4. Testing memory search...${NC}"
RESULT=$(curl -s -X POST http://localhost:3000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 1}' | jq -r '.count' 2>/dev/null || echo "-1")

if [ "$RESULT" -ge 0 ]; then
    echo -e "${GREEN}✅ Memory search working${NC}"
else
    echo -e "${RED}❌ Memory search failed${NC}"
fi

# Test 5: Model listing
echo -e "${YELLOW}5. Testing model listing...${NC}"
RESULT=$(curl -s http://localhost:3000/models | jq -r '.models[0]' 2>/dev/null || echo "ERROR")

if [ "$RESULT" != "ERROR" ]; then
    echo -e "${GREEN}✅ Model listing working${NC}"
    echo "   Available models: $(curl -s http://localhost:3000/models | jq -r '.models | join(", ")' 2>/dev/null)"
else
    echo -e "${RED}❌ Model listing failed