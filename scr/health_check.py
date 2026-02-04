"""
Health monitoring and service checks
"""
import requests
import psutil
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging
import socket

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self, services: Dict, check_interval: int = 60):
        self.services = services
        self.check_interval = check_interval
        self.last_check = 0
        self.health_status = {}
        
        # System thresholds
        self.thresholds = {
            "cpu_percent": 85,
            "memory_percent": 90,
            "disk_percent": 90,
            "temperature": 80,  # Celsius
            "response_time": 5.0  # seconds
        }
    
    def check