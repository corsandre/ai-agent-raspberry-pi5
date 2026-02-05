#!/usr/bin/env python3
"""
Main AI Agent for Docker deployment on Raspberry Pi 5
"""
import os
import sys
import json
import time
import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

# Import your modules - these will be created below
try:
    from memory_manager import PersistentMemory
    from tool_server import ToolServer
    from health_check import HealthMonitor
    from cost_tracker import CostTracker
except ImportError:
    # Create minimal versions if modules don't exist
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./logs/agent.log'),  # FIXED: Changed from /app/logs
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration
def load_config():
    config_path = Path('/app/config/agent_config.json')
    default_config = {
        "agent": {
            "name": "Pi5-AI-Agent",
            "version": "1.0.0",
            "default_model": os.getenv("DEFAULT_MODEL", "kimi-2.5k"),
            "max_history": 20,
            "temperature": 0.7,
            "max_tokens": 4000
        },
        "security": {
            "allowed_hosts": os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(","),
            "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", 10)),
            "command_timeout": int(os.getenv("COMMAND_TIMEOUT_SECONDS", 30))
        },
        "services": {
            "litellm_url": os.getenv("LITELLM_URL", "http://litellm:4000"),
            "chroma_host": os.getenv("CHROMA_HOST", "chromadb"),
            "chroma_port": int(os.getenv("CHROMA_PORT", 8000)),
            "redis_url": os.getenv("REDIS_URL", "redis://redis:6379")
        }
    }
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            user_config = json.load(f)
            # Deep merge
            for key in user_config:
                if key in default_config and isinstance(default_config[key], dict):
                    default_config[key].update(user_config[key])
                else:
                    default_config[key] = user_config[key]
    
    return default_config

# Initialize FastAPI app
app = FastAPI(
    title="Raspberry Pi 5 AI Agent",
    description="AI Assistant with persistent memory and command line access",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    project: Optional[str] = None
    stream: bool = False

class ChatResponse(BaseModel):
    response: str
    model: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    execution_time: float

class CommandRequest(BaseModel):
    command: str
    working_dir: Optional[str] = None
    timeout: Optional[int] = None

class CommandResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    return_code: int
    execution_time: float

class MemorySearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)

# Global instances
config = load_config()
memory = None
tool_server = None
health_monitor = None
cost_tracker = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global memory, tool_server, health_monitor, cost_tracker
    
    logger.info("Starting AI Agent...")
    
    try:
        # Initialize memory
        memory = PersistentMemory(
            chroma_host=config["services"]["chroma_host"],
            chroma_port=config["services"]["chroma_port"],
            workspace_dir=os.getenv("WORKSPACE_DIR", "/workspace")
        )
        logger.info("Memory initialized")
        
        # Initialize tool server
        tool_server = ToolServer(
            workspace_dir=os.getenv("WORKSPACE_DIR", "/workspace"),
            allowed_commands=config["security"].get("allowed_commands", []),
            timeout=config["security"]["command_timeout"]
        )
        logger.info("Tool server initialized")
        
        # Initialize health monitor (minimal version)
        health_monitor = type('HealthMonitor', (), {})()
        health_monitor.check_all = lambda: {"agent": {"status": "healthy"}}
        
        # Initialize cost tracker (minimal version)
        cost_tracker = type('CostTracker', (), {})()
        cost_tracker.track = lambda model, tokens: 0.0
        
        logger.info(f"AI Agent started successfully. Default model: {config['agent']['default_model']}")
        
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        return {
            "status": "healthy",
            "services": {"agent": {"status": "healthy"}},
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    background_tasks: BackgroundTasks = None
):
    """Main chat endpoint"""
    start_time = time.time()
    
    try:
        # TODO: Implement JWT verification
        # verify_token(credentials.credentials)
        
        # Build context from memory
        context = memory.retrieve_relevant_context(request.message)
        
        # Prepare messages for LLM
        messages = await prepare_messages(request.message, context, request.project)
        
        # Call LLM via LiteLLM
        model = request.model or config["agent"]["default_model"]
        llm_response = await call_llm(
            messages=messages,
            model=model,
            temperature=config["agent"]["temperature"],
            max_tokens=config["agent"]["max_tokens"],
            stream=request.stream
        )
        
        # Parse response for tool calls
        parsed_response = parse_llm_response(llm_response)
        
        # Execute tools if needed
        if parsed_response.get("tools"):
            tool_results = []
            for tool_call in parsed_response["tools"]:
                result = await execute_tool(tool_call)
                tool_results.append(result)
            
            # Update response with tool results
            parsed_response["tool_results"] = tool_results
        
        # Store conversation in memory
        memory.store_conversation(
            query=request.message,
            response=parsed_response["response"],
            metadata={
                "model": model,
                "project": request.project,
                "tools_used": len(parsed_response.get("tools", []))
            }
        )
        
        # Track cost
        tokens_used = parsed_response.get("tokens_used", 0)
        cost = cost_tracker.track(model, tokens_used)
        
        execution_time = time.time() - start_time
        
        # Background task: Update health monitor
        if background_tasks:
            background_tasks.add_task(lambda: None)  # Placeholder
        
        return ChatResponse(
            response=parsed_response["response"],
            model=model,
            tokens_used=tokens_used,
            cost=cost,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute")
async def execute_command(
    request: CommandRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Execute a shell command"""
    try:
        # TODO: Implement JWT verification
        # verify_token(credentials.credentials)
        
        result = tool_server.execute(
            command=request.command,
            working_dir=request.working_dir,
            timeout=request.timeout or config["security"]["command_timeout"]
        )
        
        return CommandResponse(**result)
        
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memory/search")
async def search_memory(
    request: MemorySearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search conversation memory"""
    try:
        # TODO: Implement JWT verification
        
        results = memory.search(
            query=request.query,
            limit=request.limit
        )
        
        return {
            "query": request.query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    """List available AI models"""
    try:
        # Query LiteLLM for available models
        import requests
        response = requests.get(f"{config['services']['litellm_url']}/models")
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"models": [config["agent"]["default_model"]]}
            
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return {"models": [config["agent"]["default_model"]]}

@app.post("/switch-model")
async def switch_model(
    model: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Switch default model"""
    try:
        # TODO: Implement JWT verification
        
        # Validate model exists
        models_response = await list_models()
        available_models = models_response.get("models", [])
        
        if model not in available_models:
            raise HTTPException(
                status_code=400,
                detail=f"Model {model} not available. Choose from: {available_models}"
            )
        
        # Update config
        config["agent"]["default_model"] = model
        
        # Save to file
        config_path = Path('/app/config/agent_config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return {"message": f"Switched to model: {model}", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def call_llm(messages: List[Dict], model: str, **kwargs) -> Dict:
    """Call LLM via LiteLLM proxy"""
    import requests
    
    payload = {
        "model": model,
        "messages": messages,
        **kwargs
    }
    
    try:
        response = requests.post(
            f"{config['services']['litellm_url']}/chat/completions",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "response": data["choices"][0]["message"]["content"],
                "tokens_used": data.get("usage", {}).get("total_tokens", 0)
            }
        else:
            logger.error(f"LLM call failed: {response.status_code} - {response.text}")
            raise Exception(f"LLM call failed: {response.status_code}")
            
    except requests.exceptions.Timeout:
        logger.error("LLM call timed out")
        raise HTTPException(status_code=504, detail="LLM request timed out")
    except Exception as e:
        logger.error(f"LLM call error: {e}")
        raise

async def execute_tool(tool_call: Dict) -> Dict:
    """Execute a tool call"""
    tool_name = tool_call["name"]
    parameters = tool_call["parameters"]
    
    if tool_name == "shell":
        return tool_server.execute(**parameters)
    elif tool_name == "read_file":
        return tool_server.read_file(**parameters)
    elif tool_name == "write_file":
        return tool_server.write_file(**parameters)
    else:
        return {"error": f"Unknown tool: {tool_name}"}

def parse_llm_response(response_text: str) -> Dict:
    """Parse LLM response for tool calls and text"""
    import re
    
    result = {
        "response": response_text,
        "tools": [],
        "tokens_used": 0
    }
    
    # Extract tool calls (simplified parsing)
    # In a real implementation, you'd use proper XML/JSON parsing
    tool_pattern = r'<tool_call>.*?</tool_call>'
    tool_matches = re.findall(tool_pattern, response_text, re.DOTALL)
    
    for match in tool_matches:
        try:
            # Simple extraction - in production use proper XML parser
            name_match = re.search(r'<name>(.*?)</name>', match)
            param_match = re.search(r'<parameters>\s*(.*?)\s*</parameters>', match, re.DOTALL)
            
            if name_match and param_match:
                tool_name = name_match.group(1).strip()
                try:
                    parameters = json.loads(param_match.group(1))
                except:
                    parameters = {"raw": param_match.group(1)}
                
                result["tools"].append({
                    "name": tool_name,
                    "parameters": parameters
                })
                
                # Remove tool call from response text
                result["response"] = result["response"].replace(match, "").strip()
                
        except Exception as e:
            logger.warning(f"Failed to parse tool call: {e}")
            continue
    
    return result

async def prepare_messages(user_message: str, context: List, project: Optional[str] = None) -> List[Dict]:
    """Prepare messages for LLM with context"""
    system_prompt = f"""You are an AI assistant running on a Raspberry Pi 5 with:
- Access to shell commands (use <tool_call> for commands)
- File system access (read/write files in workspace)
- Persistent memory (context from previous conversations)

Workspace: {os.getenv('WORKSPACE_DIR', '/workspace')}
Current project: {project or 'No project specified'}

Available tools:
1. shell - Execute shell command. Parameters: {{"command": "ls -la", "working_dir": "/optional/path"}}
2. read_file - Read file content. Parameters: {{"path": "/path/to/file"}}
3. write_file - Write to file. Parameters: {{"path": "/path/to/file", "content": "text"}}

Format tool calls as:
<tool_call>
<name>tool_name</name>
<parameters>
{{"param1": "value1"}}
</parameters>
</tool_call>

Relevant context from previous conversations:
{json.dumps(context, indent=2)}

Always think step by step. If you need to execute commands or read files, use tool calls.
Be concise but helpful. For coding tasks, provide complete, working examples."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    return messages

if __name__ == "__main__":
    # Get host and port from environment
    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "3000"))
    
    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )