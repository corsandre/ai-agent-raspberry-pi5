"""
Tool Server for safe command execution and file operations
"""
import subprocess
import os
import shlex
import tempfile
from pathlib import Path
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
import shutil

logger = logging.getLogger(__name__)

class ToolServer:
    def __init__(self, workspace_dir: str = "/workspace", 
                 allowed_commands: List[str] = None,
                 timeout: int = 30):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Default allowed commands (safe subset)
        self.allowed_commands = allowed_commands or [
            "ls", "cd", "pwd", "cat", "grep", "find", "mkdir", "touch",
            "cp", "mv", "rm", "chmod", "chown", "python", "python3",
            "pip", "git", "docker", "npm", "node", "echo", "curl", "wget",
            "ssh", "scp", "rsync", "tar", "zip", "unzip", "df", "du",
            "head", "tail", "wc", "sort", "uniq", "diff", "patch"
        ]
        
        # Restricted paths
        self.restricted_paths = [
            "/etc", "/root", "/boot", "/proc", "/sys",
            "/var/lib", "/usr/lib", "/lib", "/bin", "/sbin"
        ]
        
        self.timeout = timeout
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
        logger.info(f"Tool server initialized. Workspace: {self.workspace_dir}")
    
    def is_safe_command(self, command: str) -> Tuple[bool, str]:
        """Check if command is safe to execute"""
        try:
            # Parse command
            parts = shlex.split(command)
            if not parts:
                return False, "Empty command"
            
            # Get base command (strip path)
            base_cmd = parts[0].split('/')[-1]
            
            # Check against allowed commands
            if base_cmd not in self.allowed_commands:
                return False, f"Command '{base_cmd}' not in allowed list"
            
            # Check for dangerous patterns
            dangerous_patterns = [
                "rm -rf /", "mkfs", "dd", "> /dev/sda", "chmod 777 /",
                ":(){ :|:& };:", "fork()", "exec(", "system(",
                "shutdown", "reboot", "halt", "poweroff"
            ]
            
            cmd_lower = command.lower()
            for pattern in dangerous_patterns:
                if pattern in cmd_lower:
                    return False, f"Command contains dangerous pattern: {pattern}"
            
            # Check for path traversal
            if ".." in command and any(x in command for x in ["/etc", "/root", "/boot"]):
                return False, "Path traversal attempt detected"
            
            return True, "OK"
        
        except Exception as e:
            return False, f"Command parsing error: {str(e)}"
    
    def is_safe_path(self, path: str) -> Tuple[bool, str]:
        """Check if path is safe to access"""
        try:
            # Resolve path
            resolved = Path(path).resolve()
            
            # Check if within restricted paths
            for restricted in self.restricted_paths:
                if str(resolved).startswith(restricted):
                    return False, f"Path is in restricted area: {restricted}"
            
            # Check for path traversal
            if ".." in str(resolved) and not str(resolved).startswith(str(self.workspace_dir)):
                return False, "Path traversal outside workspace"
            
            # For writes, ensure it's in workspace
            if not str(resolved).startswith(str(self.workspace_dir)):
                return False, "Can only write to workspace"
            
            return True, "OK"
        
        except Exception as e:
            return False, f"Path validation error: {str(e)}"
    
    def execute(self, command: str, working_dir: Optional[str] = None, 
                timeout: Optional[int] = None) -> Dict:
        """Execute a shell command safely"""
        start_time = time.time()
        
        # Validate command
        is_safe, message = self.is_safe_command(command)
        if not is_safe:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Security violation: {message}",
                "return_code": 1,
                "execution_time": time.time() - start_time
            }
        
        # Set working directory
        cwd = self.workspace_dir
        if working_dir:
            safe, msg = self.is_safe_path(working_dir)
            if safe:
                cwd = Path(working_dir)
                cwd.mkdir(parents=True, exist_ok=True)
            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Invalid working directory: {msg}",
                    "return_code": 1,
                    "execution_time": time.time() - start_time
                }
        
        # Prepare environment
        env = os.environ.copy()
        env["PATH"] = f"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:{env.get('PATH', '')}"
        
        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            execution_time = time.time() - start_time
            
            logger.info(f"Executed command: {command[:100]}... (took {execution_time:.2f}s)")
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "execution_time": execution_time,
                "working_dir": str(cwd)
            }
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.warning(f"Command timed out: {command[:100]}...")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout or self.timeout} seconds",
                "return_code": -1,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Command execution error: {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "return_code": -1,
                "execution_time": execution_time
            }
    
    def read_file(self, path: str, encoding: str = "utf-8") -> Dict:
        """Read file contents"""
        try:
            # Validate path
            safe, message = self.is_safe_path(path)
            if not safe:
                return {"success": False, "error": message, "content": ""}
            
            file_path = Path(path)
            
            # Check if exists
            if not file_path.exists():
                return {"success": False, "error": "File not found", "content": ""}
            
            # Check if too large
            if file_path.stat().st_size > self.max_file_size:
                return {
                    "success": False, 
                    "error": f"File too large ({file_path.stat().st_size} > {self.max_file_size})",
                    "content": ""
                }
            
            # Read file
            try:
                content = file_path.read_text(encoding=encoding, errors='ignore')
            except:
                # Try binary mode for non-text files
                content = file_path.read_bytes()
                return {
                    "success": True,
                    "content": content,
                    "size": len(content),
                    "is_binary": True,
                    "encoding": "binary"
                }
            
            return {
                "success": True,
                "content": content,
                "size": len(content),
                "is_binary": False,
                "encoding": encoding
            }
            
        except Exception as e:
            logger.error(f"File read error: {str(e)}")
            return {"success": False, "error": str(e), "content": ""}
    
    def write_file(self, path: str, content: str, encoding: str = "utf-8") -> Dict:
        """Write to file"""
        try:
            # Validate path
            safe, message = self.is_safe_path(path)
            if not safe:
                return {"success": False, "error": message}
            
            file_path = Path(path)
            
            # Create directory if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check content size
            if len(content) > self.max_file_size:
                return {
                    "success": False,
                    "error": f"Content too large ({len(content)} > {self.max_file_size})"
                }
            
            # Write file
            if isinstance(content, str):
                file_path.write_text(content, encoding=encoding)
            else:
                # Binary content
                file_path.write_bytes(content)
            
            logger.info(f"Written file: {path} ({len(content)} bytes)")
            
            return {
                "success": True,
                "path": str(file_path),
                "size": len(content),
                "created": not file_path.exists()  # Was it created or overwritten?
            }
            
        except Exception as e:
            logger.error(f"File write error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def list_directory(self, path: str = None) -> Dict:
        """List directory contents"""
        try:
            target_dir = self.workspace_dir
            if path:
                safe, message = self.is_safe_path(path)
                if not safe:
                    return {"success": False, "error": message, "files": []}
                target_dir = Path(path)
            
            if not target_dir.exists():
                return {"success": False, "error": "Directory not found", "files": []}
            
            if not target_dir.is_dir():
                return {"success": False, "error": "Not a directory", "files": []}
            
            files = []
            for item in target_dir.iterdir():
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else 0,
                        "modified": stat.st_mtime,
                        "permissions": oct(stat.st_mode)[-3:],
                        "path": str(item.relative_to(self.workspace_dir))
                    })
                except:
                    # Skip files we can't stat
                    continue
            
            return {
                "success": True,
                "path": str(target_dir),
                "files": sorted(files, key=lambda x: (x["type"] == "directory", x["name"])),
                "count": len(files)
            }
            
        except Exception as e:
            logger.error(f"Directory listing error: {str(e)}")
            return {"success": False, "error": str(e), "files": []}
    
    def get_file_info(self, path: str) -> Dict:
        """Get file information"""
        try:
            safe, message = self.is_safe_path(path)
            if not safe:
                return {"success": False, "error": message}
            
            file_path = Path(path)
            
            if not file_path.exists():
                return {"success": False, "error": "File not found"}
            
            stat = file_path.stat()
            
            return {
                "success": True,
                "name": file_path.name,
                "path": str(file_path),
                "type": "directory" if file_path.is_dir() else "file",
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "accessed": stat.st_atime,
                "permissions": oct(stat.st_mode)[-3:],
                "owner": stat.st_uid,
                "group": stat.st_gid,
                "extension": file_path.suffix,
                "absolute_path": str(file_path.resolve())
            }
            
        except Exception as e:
            logger.error(f"File info error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_directory(self, path: str) -> Dict:
        """Create a directory"""
        try:
            safe, message = self.is_safe_path(path)
            if not safe:
                return {"success": False, "error": message}
            
            dir_path = Path(path)
            
            # Create directory
            dir_path.mkdir(parents=True, exist_ok=True)
            
            return {
                "success": True,
                "path": str(dir_path),
                "created": True,
                "message": f"Directory created: {path}"
            }
            
        except Exception as e:
            logger.error(f"Create directory error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def delete_path(self, path: str, recursive: bool = False) -> Dict:
        """Delete a file or directory"""
        try:
            safe, message = self.is_safe_path(path)
            if not safe:
                return {"success": False, "error": message}
            
            target_path = Path(path)
            
            if not target_path.exists():
                return {"success": False, "error": "Path not found"}
            
            # Extra safety: never delete workspace root
            if target_path.resolve() == self.workspace_dir.resolve():
                return {"success": False, "error": "Cannot delete workspace root"}
            
            if target_path.is_dir():
                if recursive:
                    shutil.rmtree(target_path)
                else:
                    target_path.rmdir()
            else:
                target_path.unlink()
            
            logger.warning(f"Deleted path: {path} (recursive: {recursive})")
            
            return {
                "success": True,
                "path": str(target_path),
                "deleted": True,
                "message": f"Deleted: {path}"
            }
            
        except Exception as e:
            logger.error(f"Delete error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def search_files(self, pattern: str, directory: str = None, recursive: bool = True) -> Dict:
        """Search for files matching pattern"""
        try:
            search_dir = self.workspace_dir
            if directory:
                safe, message = self.is_safe_path(directory)
                if not safe:
                    return {"success": False, "error": message, "results": []}
                search_dir = Path(directory)
            
            if not search_dir.exists():
                return {"success": False, "error": "Directory not found", "results": []}
            
            results = []
            method = search_dir.rglob if recursive else search_dir.glob
            
            for file_path in method(pattern):
                try:
                    if file_path.is_file():
                        stat = file_path.stat()
                        results.append({
                            "path": str(file_path.relative_to(self.workspace_dir)),
                            "name": file_path.name,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            "absolute_path": str(file_path)
                        })
                except:
                    continue
            
            return {
                "success": True,
                "pattern": pattern,
                "directory": str(search_dir),
                "recursive": recursive,
                "results": sorted(results, key=lambda x: x["path"]),
                "count": len(results)
            }
            
        except Exception as e:
            logger.error(f"File search error: {str(e)}")
            return {"success": False, "error": str(e), "results": []}