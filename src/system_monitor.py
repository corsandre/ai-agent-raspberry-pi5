"""
System Monitor for AI Agent
Monitors system resources, Docker containers, and service health
"""
import psutil
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import socket
import requests
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.monitoring_interval = self.config.get("monitoring_interval", 60)  # seconds
        self.log_file = Path(self.config.get("log_file", "/app/logs/system_monitor.log"))
        self.alerts_file = Path(self.config.get("alerts_file", "/app/logs/alerts.jsonl"))
        
        # Thresholds
        self.thresholds = {
            "cpu_percent": self.config.get("cpu_threshold", 85),
            "memory_percent": self.config.get("memory_threshold", 90),
            "disk_percent": self.config.get("disk_threshold", 90),
            "temperature": self.config.get("temperature_threshold", 80),  # Celsius
            "response_time": self.config.get("response_time_threshold", 5.0),  # seconds
        }
        
        # Services to monitor
        self.services = {
            "ai_agent": {
                "url": "http://localhost:3000/health",
                "timeout": 5,
                "required": True
            },
            "litellm": {
                "url": "http://localhost:4000/health",
                "timeout": 5,
                "required": True
            },
            "chromadb": {
                "url": "http://localhost:8000/api/v1/heartbeat",
                "timeout": 10,
                "required": True
            },
            "redis": {
                "check": "docker",  # Special check via Docker
                "container": "ai-agent-redis",
                "required": True
            }
        }
        
        # Monitoring state
        self.monitoring = False
        self.thread = None
        
        # Create log directory
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"System Monitor initialized. Interval: {self.monitoring_interval}s")
    
    def get_system_stats(self) -> Dict:
        """Get current system statistics"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory
            memory = psutil.virtual_memory()
            
            # Disk
            disk = psutil.disk_usage('/')
            
            # Network
            net_io = psutil.net_io_counters()
            
            # Temperature (Raspberry Pi specific)
            temperature = self.get_cpu_temperature()
            
            # Docker stats (if available)
            docker_stats = self.get_docker_stats()
            
            stats = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "count_logical": psutil.cpu_count(logical=True),
                    "frequency": psutil.cpu_freq().current if psutil.cpu_freq() else None
                },
                "memory": {
                    "percent": memory.percent,
                    "total_gb": memory.total / (1024**3),
                    "used_gb": memory.used / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "free_gb": memory.free / (1024**3)
                },
                "disk": {
                    "percent": disk.percent,
                    "total_gb": disk.total / (1024**3),
                    "used_gb": disk.used / (1024**3),
                    "free_gb": disk.free / (1024**3)
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "system": {
                    "temperature": temperature,
                    "load_avg": psutil.getloadavg(),
                    "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                    "users": len(psutil.users())
                },
                "docker": docker_stats,
                "alerts": self.check_thresholds(cpu_percent, memory.percent, disk.percent, temperature)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def get_cpu_temperature(self) -> Optional[float]:
        """Get CPU temperature (Raspberry Pi specific)"""
        try:
            # Try different temperature file locations
            temp_files = [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/hwmon/hwmon0/temp1_input",
                "/sys/class/hwmon/hwmon1/temp1_input"
            ]
            
            for temp_file in temp_files:
                if Path(temp_file).exists():
                    with open(temp_file, "r") as f:
                        temp = float(f.read().strip())
                        # Convert to Celsius
                        if temp > 1000:  # If in millidegrees
                            temp = temp / 1000
                        return temp
            
            return None
        except:
            return None
    
    def get_docker_stats(self) -> Dict:
        """Get Docker container statistics"""
        try:
            import docker
            client = docker.from_env()
            
            containers = client.containers.list(all=True)
            stats = {
                "total": len(containers),
                "running": len([c for c in containers if c.status == "running"]),
                "containers": []
            }
            
            for container in containers[:10]:  # Limit to first 10
                try:
                    container_stats = container.stats(stream=False)
                    
                    # Parse CPU usage
                    cpu_stats = container_stats.get('cpu_stats', {})
                    precpu_stats = container_stats.get('precpu_stats', {})
                    
                    cpu_delta = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - \
                               precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                    system_delta = cpu_stats.get('system_cpu_usage', 0) - \
                                  precpu_stats.get('system_cpu_usage', 0)
                    
                    cpu_percent = 0.0
                    if system_delta > 0 and cpu_delta > 0:
                        cpu_percent = (cpu_delta / system_delta) * \
                                     len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', [])) * 100
                    
                    # Parse memory usage
                    memory_stats = container_stats.get('memory_stats', {})
                    memory_usage = memory_stats.get('usage', 0)
                    memory_limit = memory_stats.get('limit', 0)
                    memory_percent = 0.0
                    if memory_limit > 0:
                        memory_percent = (memory_usage / memory_limit) * 100
                    
                    stats["containers"].append({
                        "name": container.name,
                        "status": container.status,
                        "image": container.image.tags[0] if container.image.tags else "unknown",
                        "cpu_percent": round(cpu_percent, 2),
                        "memory_percent": round(memory_percent, 2),
                        "memory_used_mb": round(memory_usage / (1024**2), 2),
                        "memory_limit_mb": round(memory_limit / (1024**2), 2),
                        "network_io": container_stats.get('networks', {}),
                        "created": container.attrs['Created']
                    })
                    
                except Exception as e:
                    logger.warning(f"Error getting stats for container {container.name}: {e}")
                    continue
            
            return stats
            
        except ImportError:
            logger.warning("Docker Python library not installed")
            return {"error": "docker library not available"}
        except Exception as e:
            logger.error(f"Error getting Docker stats: {e}")
            return {"error": str(e)}
    
    def check_service_health(self) -> Dict:
        """Check health of all monitored services"""
        results = {}
        
        for service_name, service_config in self.services.items():
            try:
                start_time = time.time()
                
                if service_config.get("check") == "docker":
                    # Docker-specific check
                    import docker
                    client = docker.from_env()
                    container = client.containers.get(service_config["container"])
                    
                    if container.status == "running":
                        # Try to ping Redis
                        if service_name == "redis":
                            exec_result = container.exec_run("redis-cli ping")
                            is_healthy = "PONG" in exec_result.output.decode()
                        else:
                            is_healthy = True
                        
                        results[service_name] = {
                            "status": "healthy" if is_healthy else "unhealthy",
                            "latency_ms": round((time.time() - start_time) * 1000, 2),
                            "container_status": container.status,
                            "error": None if is_healthy else "Container running but service not responding"
                        }
                    else:
                        results[service_name] = {
                            "status": "unhealthy",
                            "latency_ms": round((time.time() - start_time) * 1000, 2),
                            "container_status": container.status,
                            "error": f"Container status: {container.status}"
                        }
                        
                else:
                    # HTTP check
                    response = requests.get(
                        service_config["url"],
                        timeout=service_config["timeout"]
                    )
                    
                    latency_ms = round((time.time() - start_time) * 1000, 2)
                    
                    if response.status_code == 200:
                        results[service_name] = {
                            "status": "healthy",
                            "latency_ms": latency_ms,
                            "response_code": response.status_code,
                            "error": None
                        }
                    else:
                        results[service_name] = {
                            "status": "unhealthy",
                            "latency_ms": latency_ms,
                            "response_code": response.status_code,
                            "error": f"HTTP {response.status_code}"
                        }
                        
            except requests.exceptions.Timeout:
                results[service_name] = {
                    "status": "unhealthy",
                    "latency_ms": service_config["timeout"] * 1000,
                    "error": "Request timeout"
                }
            except Exception as e:
                results[service_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # Determine overall health
        unhealthy_services = [
            name for name, result in results.items()
            if result["status"] != "healthy" and self.services[name].get("required", False)
        ]
        
        results["_overall"] = {
            "status": "healthy" if not unhealthy_services else "unhealthy",
            "unhealthy_services": unhealthy_services,
            "timestamp": datetime.now().isoformat()
        }
        
        return results
    
    def check_thresholds(self, cpu_percent: float, memory_percent: float, 
                        disk_percent: float, temperature: Optional[float]) -> List[Dict]:
        """Check if any thresholds are exceeded"""
        alerts = []
        
        # CPU check
        if cpu_percent > self.thresholds["cpu_percent"]:
            alerts.append({
                "level": "warning",
                "type": "cpu",
                "message": f"CPU usage high: {cpu_percent:.1f}% (threshold: {self.thresholds['cpu_percent']}%)",
                "value": cpu_percent,
                "threshold": self.thresholds["cpu_percent"]
            })
        
        # Memory check
        if memory_percent > self.thresholds["memory_percent"]:
            alerts.append({
                "level": "warning",
                "type": "memory",
                "message": f"Memory usage high: {memory_percent:.1f}% (threshold: {self.thresholds['memory_percent']}%)",
                "value": memory_percent,
                "threshold": self.thresholds["memory_percent"]
            })
        
        # Disk check
        if disk_percent > self.thresholds["disk_percent"]:
            alerts.append({
                "level": "critical",
                "type": "disk",
                "message": f"Disk usage high: {disk_percent:.1f}% (threshold: {self.thresholds['disk_percent']}%)",
                "value": disk_percent,
                "threshold": self.thresholds["disk_percent"]
            })
        
        # Temperature check
        if temperature and temperature > self.thresholds["temperature"]:
            alerts.append({
                "level": "critical",
                "type": "temperature",
                "message": f"CPU temperature high: {temperature:.1f}°C (threshold: {self.thresholds['temperature']}°C)",
                "value": temperature,
                "threshold": self.thresholds["temperature"]
            })
        
        # Log alerts if any
        if alerts:
            self.log_alerts(alerts)
        
        return alerts
    
    def log_alerts(self, alerts: List[Dict]):
        """Log alerts to file"""
        try:
            alert_entry = {
                "timestamp": datetime.now().isoformat(),
                "alerts": alerts
            }
            
            with open(self.alerts_file, "a") as f:
                f.write(json.dumps(alert_entry) + "\n")
            
            # Also log to console for critical alerts
            critical_alerts = [a for a in alerts if a["level"] == "critical"]
            for alert in critical_alerts:
                logger.warning(f"CRITICAL ALERT: {alert['message']}")
                
        except Exception as e:
            logger.error(f"Error logging alerts: {e}")
    
    def log_monitoring_data(self, system_stats: Dict, service_health: Dict):
        """Log monitoring data to file"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "system": system_stats,
                "services": service_health
            }
            
            with open(self.log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            logger.error(f"Error logging monitoring data: {e}")
    
    def start_monitoring(self):
        """Start continuous monitoring in background thread"""
        if self.monitoring:
            logger.warning("Monitoring already started")
            return
        
        self.monitoring = True
        
        def monitor_loop():
            logger.info("Starting system monitoring loop")
            
            while self.monitoring:
                try:
                    # Collect data
                    system_stats = self.get_system_stats()
                    service_health = self.check_service_health()
                    
                    # Log data
                    self.log_monitoring_data(system_stats, service_health)
                    
                    # Check for critical alerts
                    alerts = system_stats.get("alerts", [])
                    critical_alerts = [a for a in alerts if a["level"] == "critical"]
                    
                    if critical_alerts:
                        logger.warning(f"Critical alerts detected: {len(critical_alerts)}")
                    
                    # Sleep until next interval
                    time.sleep(self.monitoring_interval)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(10)  # Shorter sleep on error
        
        # Start monitoring thread
        self.thread = threading.Thread(target=monitor_loop, daemon=True)
        self.thread.start()
        
        logger.info(f"System monitoring started (interval: {self.monitoring_interval}s)")
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("System monitoring stopped")
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent alerts from log file"""
        alerts = []
        
        try:
            if not self.alerts_file.exists():
                return alerts
            
            with open(self.alerts_file, "r") as f:
                lines = f.readlines()
            
            # Parse last N lines
            for line in lines[-limit:]:
                try:
                    alert_data = json.loads(line.strip())
                    alerts.append(alert_data)
                except:
                    continue
            
            return alerts[::-1]  # Reverse to show newest first
            
        except Exception as e:
            logger.error(f"Error reading alerts: {e}")
            return []
    
    def get_monitoring_summary(self) -> Dict:
        """Get a summary of current monitoring state"""
        system_stats = self.get_system_stats()
        service_health = self.check_service_health()
        
        # Calculate uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        # Get recent alerts
        recent_alerts = self.get_recent_alerts(5)
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "uptime": str(uptime),
            "system": {
                "cpu_percent": system_stats.get("cpu", {}).get("percent", 0),
                "memory_percent": system_stats.get("memory", {}).get("percent", 0),
                "disk_percent": system_stats.get("disk", {}).get("percent", 0),
                "temperature": system_stats.get("system", {}).get("temperature")
            },
            "services": {
                "total": len(service_health) - 1,  # Exclude _overall
                "healthy": len([v for k, v in service_health.items() 
                              if k != "_overall" and v.get("status") == "healthy"]),
                "unhealthy": len([v for k, v in service_health.items() 
                                if k != "_overall" and v.get("status") != "healthy"])
            },
            "overall_health": service_health.get("_overall", {}).get("status", "unknown"),
            "recent_alerts": recent_alerts,
            "monitoring_active": self.monitoring
        }
        
        return summary