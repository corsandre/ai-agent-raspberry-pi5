import os
import json
from pathlib import Path
import subprocess
import shlex

class ToolServer:
    def __init__(self, workspace_dir="/workspace", allowed_commands=None, timeout=30):
        self.workspace_dir = workspace_dir
        self.allowed_commands = allowed_commands or [
            "ls", "cd", "pwd", "cat", "grep", "find", "mkdir", "touch",
            "cp", "mv", "rm", "chmod", "chown", "python", "python3",
            "pip", "git", "docker", "npm", "node", "echo", "curl", "wget"
        ]
        self.timeout = timeout
        
    def execute(self, command: str, working_dir: str = None, timeout: int = None):
        """Execute a shell command safely"""
        import time
        
        start_time = time.time()
        
        if not self._is_safe_command(command):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command not allowed",
                "return_code": -1,
                "execution_time": 0
            }
        
        # Set working directory
        cwd = working_dir or self.workspace_dir
        
        # Ensure directory exists
        Path(cwd).mkdir(parents=True, exist_ok=True)
        
        try:
            # Execute command with timeout
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout
            )
            
            execution_time = time.time() - start_time
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "execution_time": execution_time
            }
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout or self.timeout}s",
                "return_code": -1,
                "execution_time": execution_time
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "execution_time": execution_time
            }
    
    def read_file(self, path: str):
        """Read file contents"""
        safe_path = Path(path).resolve()
        
        # Prevent path traversal
        if ".." in str(safe_path):
            return {"error": "Path traversal not allowed"}
        
        if not safe_path.exists():
            return {"error": "File not found"}
        
        if safe_path.is_dir():
            # List directory
            files = []
            for f in safe_path.iterdir():
                files.append({
                    "name": f.name,
                    "type": "directory" if f.is_dir() else "file",
                    "size": f.stat().st_size if f.is_file() else 0
                })
            return {"path": str(safe_path), "files": files}
        else:
            # Read file
            try:
                content = safe_path.read_text()
                return {
                    "path": str(safe_path),
                    "content": content,
                    "size": len(content)
                }
            except Exception as e:
                return {"error": f"Cannot read file: {str(e)}"}
    
    def write_file(self, path: str, content: str):
        """Write file contents"""
        safe_path = Path(path).resolve()
        
        # Only allow writing to workspace
        if not str(safe_path).startswith(str(Path(self.workspace_dir).resolve())):
            return {"error": "Can only write to workspace"}
        
        # Create directory if needed
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            safe_path.write_text(content)
            return {"success": True, "path": str(safe_path)}
        except Exception as e:
            return {"error": f"Cannot write file: {str(e)}"}
    
    def _is_safe_command(self, command: str) -> bool:
        """Validate command safety"""
        try:
            # Parse command
            parts = shlex.split(command)
            if not parts:
                return False
            
            # Check base command
            base_cmd = parts[0].split('/')[-1]  # Remove path
            
            # Check against whitelist
            if base_cmd not in self.allowed_commands:
                return False
            
            # Check for dangerous patterns
            dangerous_patterns = [
                "rm -rf /", "mkfs", "dd", "> /dev/sda",
                ":(){ :|:& };:", "chmod 777 /"
            ]
            
            cmd_lower = command.lower()
            for pattern in dangerous_patterns:
                if pattern in cmd_lower:
                    return False
            
            return True
        except:
            return False

class DockerAIAgent:
    def __init__(self):
        # Docker-specific paths
        self.workspace_dir = os.getenv("WORKSPACE_DIR", "/home/aiagent/ai-workspace")
        self.data_dir = os.getenv("DATA_DIR", "/data")
        self.logs_dir = "/app/logs"
        
        # Service discovery (Docker Compose network)
        self.services = {
            "redis": os.getenv("REDIS_HOST", "redis"),
            "chromadb": os.getenv("CHROMA_HOST", "chromadb"),
            "litellm": os.getenv("LITELLM_URL", "http://litellm:4000")
        }
        
        # Create necessary directories
        self.setup_directories()
    
    def setup_directories(self):
        """Create required directories with proper permissions"""
        dirs = [
            self.workspace_dir,
            self.data_dir,
            self.logs_dir,
            f"{self.data_dir}/chroma",
            f"{self.data_dir}/sqlite"
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            # Ensure writable by non-root user
            os.chmod(dir_path, 0o755)
    
    def get_host_ip(self):
        """Get Docker host IP for SSH/SCP operations"""
        try:
            # In Docker, gateway is usually host
            import socket
            return socket.gethostbyname("host.docker.internal")
        except:
            # Fallback for Linux
            return "172.17.0.1"  # Default Docker bridge gateway
    
    def execute_safe(self, command):
        """A simple safe command executor."""
        import subprocess
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out", "return_code": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1}
    
    def execute_in_container(self, command: str, container: str = None):
        """Execute command in another container or host"""
        if container:
            # Use docker exec
            docker_cmd = f"docker exec {container} {command}"
            return self.execute_safe(docker_cmd)
        else:
            # Execute in current container
            return self.execute_safe(command)