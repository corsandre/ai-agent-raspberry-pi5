"""
Cost Tracker for AI Agent
Tracks API usage costs across different models
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path
from collections import defaultdict
import sqlite3

logger = logging.getLogger(__name__)

class CostTracker:
    def __init__(self, db_path: str = "/app/data/costs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Model pricing (per 1M tokens)
        # These are example prices, update based on actual provider pricing
        self.model_pricing = {
            # Kimi models
            "kimi-2.5k": {"input": 0.06, "output": 0.24},  # $ per 1M tokens
            "kimi-1.8k": {"input": 0.012, "output": 0.012},
            
            # OpenAI models
            "gpt-4o": {"input": 5.00, "output": 15.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
            
            # Anthropic models
            "claude-3-opus": {"input": 15.00, "output": 75.00},
            "claude-3-sonnet": {"input": 3.00, "output": 15.00},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
            
            # Local models (free)
            "local-codellama": {"input": 0.00, "output": 0.00},
            "local-phi": {"input": 0.00, "output": 0.00},
            "local-mistral": {"input": 0.00, "output": 0.00},
            
            # Default fallback
            "default": {"input": 1.00, "output": 3.00}
        }
        
        # Initialize database
        self._init_database()
        
        # Cache for daily/monthly totals
        self._cache = {}
        self._cache_expiry = {}
        
        logger.info(f"Cost Tracker initialized. Database: {self.db_path}")
    
    def _init_database(self):
        """Initialize SQLite database for cost tracking"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create usage table
        c.execute('''
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                model TEXT NOT NULL,
                provider TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                input_cost REAL DEFAULT 0.0,
                output_cost REAL DEFAULT 0.0,
                total_cost REAL DEFAULT 0.0,
                request_duration REAL DEFAULT 0.0,
                user_id TEXT,
                project TEXT,
                api_key_hash TEXT,
                metadata TEXT
            )
        ''')
        
        # Create daily summary table
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                date DATE PRIMARY KEY,
                total_requests INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                model_breakdown TEXT,
                provider_breakdown TEXT
            )
        ''')
        
        # Create monthly summary table
        c.execute('''
            CREATE TABLE IF NOT EXISTS monthly_summary (
                year_month TEXT PRIMARY KEY,
                total_requests INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                daily_breakdown TEXT
            )
        ''')
        
        # Create indexes for faster queries
        c.execute('CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage(timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_usage_model ON usage(model)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_usage_user ON usage(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_usage_project ON usage(project)')
        
        conn.commit()
        conn.close()
    
    def get_model_cost(self, model: str, input_tokens: int, output_tokens: int) -> Dict[str, float]:
        """Calculate cost for a given model and token counts"""
        pricing = self.model_pricing.get(model, self.model_pricing["default"])
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }
    
    def track_usage(self, model: str, input_tokens: int, output_tokens: int, 
                   user_id: Optional[str] = None, project: Optional[str] = None,
                   provider: Optional[str] = None, request_duration: float = 0.0,
                   api_key_hash: Optional[str] = None, metadata: Dict = None) -> Dict:
        """Track API usage and calculate cost"""
        # Calculate costs
        costs = self.get_model_cost(model, input_tokens, output_tokens)
        
        # Determine provider if not specified
        if not provider:
            if model.startswith("kimi"):
                provider = "moonshot"
            elif model.startswith("gpt"):
                provider = "openai"
            elif model.startswith("claude"):
                provider = "anthropic"
            elif model.startswith("local"):
                provider = "local"
            else:
                provider = "unknown"
        
        # Store in database
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO usage 
            (timestamp, model, provider, input_tokens, output_tokens, total_tokens,
             input_cost, output_cost, total_cost, request_duration, user_id, project,
             api_key_hash, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            model,
            provider,
            input_tokens,
            output_tokens,
            costs["total_tokens"],
            costs["input_cost"],
            costs["output_cost"],
            costs["total_cost"],
            request_duration,
            user_id,
            project,
            api_key_hash,
            json.dumps(metadata or {})
        ))
        
        usage_id = c.lastrowid
        
        # Update daily summary
        today = datetime.now().date().isoformat()
        c.execute('''
            INSERT OR REPLACE INTO daily_summary (date, total_requests, total_tokens, total_cost)
            VALUES (?, 
                COALESCE((SELECT total_requests FROM daily_summary WHERE date = ?), 0) + 1,
                COALESCE((SELECT total_tokens FROM daily_summary WHERE date = ?), 0) + ?,
                COALESCE((SELECT total_cost FROM daily_summary WHERE date = ?), 0) + ?
            )
        ''', (today, today, today, costs["total_tokens"], today, costs["total_cost"]))
        
        conn.commit()
        conn.close()
        
        # Invalidate cache
        self._invalidate_cache()
        
        logger.info(f"Tracked usage: {model} - {costs['total_tokens']} tokens - ${costs['total_cost']:.6f}")
        
        return {
            "usage_id": usage_id,
            "model": model,
            "costs": costs,
            "provider": provider,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_daily_summary(self, date: Optional[str] = None) -> Dict:
        """Get summary for a specific day (default: today)"""
        if not date:
            date = datetime.now().date().isoformat()
        
        cache_key = f"daily_{date}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get daily total
        c.execute('''
            SELECT 
                COALESCE(total_requests, 0) as requests,
                COALESCE(total_tokens, 0) as tokens,
                COALESCE(total_cost, 0.0) as cost
            FROM daily_summary 
            WHERE date = ?
        ''', (date,))
        
        row = c.fetchone()
        if not row:
            result = {
                "date": date,
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
                "breakdown": {}
            }
            self._cache[cache_key] = result
            self._cache_expiry[cache_key] = time.time() + 60  # Cache for 1 minute
            return result
        
        requests, tokens, cost = row
        
        # Get breakdown by model
        c.execute('''
            SELECT 
                model,
                COUNT(*) as request_count,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(input_cost) as input_cost,
                SUM(output_cost) as output_cost,
                SUM(total_cost) as total_cost
            FROM usage
            WHERE DATE(timestamp) = DATE(?)
            GROUP BY model
            ORDER BY total_cost DESC
        ''', (date,))
        
        breakdown = []
        for row in c.fetchall():
            breakdown.append({
                "model": row[0],
                "requests": row[1],
                "input_tokens": row[2],
                "output_tokens": row[3],
                "total_tokens": row[4],
                "input_cost": row[5],
                "output_cost": row[6],
                "total_cost": row[7]
            })
        
        # Get breakdown by provider
        c.execute('''
            SELECT 
                provider,
                COUNT(*) as request_count,
                SUM(total_tokens) as total_tokens,
                SUM(total_cost) as total_cost
            FROM usage
            WHERE DATE(timestamp) = DATE(?)
            GROUP BY provider
            ORDER BY total_cost DESC
        ''', (date,))
        
        provider_breakdown = []
        for row in c.fetchall():
            provider_breakdown.append({
                "provider": row[0],
                "requests": row[1],
                "tokens": row[2],
                "cost": row[3]
            })
        
        conn.close()
        
        result = {
            "date": date,
            "requests": requests,
            "tokens": tokens,
            "cost": round(cost, 6),
            "breakdown": {
                "by_model": breakdown,
                "by_provider": provider_breakdown
            }
        }
        
        self._cache[cache_key] = result
        self._cache_expiry[cache_key] = time.time() + 60  # Cache for 1 minute
        
        return result
    
    def get_monthly_summary(self, year: Optional[int] = None, month: Optional[int] = None) -> Dict:
        """Get summary for a specific month (default: current month)"""
        now = datetime.now()
        if not year:
            year = now.year
        if not month:
            month = now.month
        
        year_month = f"{year}-{month:02d}"
        cache_key = f"monthly_{year_month}"
        
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Calculate monthly totals
        c.execute('''
            SELECT 
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM usage
            WHERE strftime('%Y-%m', timestamp) = ?
        ''', (year_month,))
        
        row = c.fetchone()
        requests = row[0] or 0
        tokens = row[1] or 0
        cost = row[2] or 0.0
        
        # Get daily breakdown for the month
        c.execute('''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM usage
            WHERE strftime('%Y-%m', timestamp) = ?
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''', (year_month,))
        
        daily_breakdown = []
        for row in c.fetchall():
            daily_breakdown.append({
                "date": row[0],
                "requests": row[1],
                "tokens": row[2],
                "cost": row[3]
            })
        
        # Get model breakdown
        c.execute('''
            SELECT 
                model,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM usage
            WHERE strftime('%Y-%m', timestamp) = ?
            GROUP BY model
            ORDER BY cost DESC
        ''', (year_month,))
        
        model_breakdown = []
        for row in c.fetchall():
            model_breakdown.append({
                "model": row[0],
                "requests": row[1],
                "tokens": row[2],
                "cost": row[3]
            })
        
        conn.close()
        
        result = {
            "year_month": year_month,
            "requests": requests,
            "tokens": tokens,
            "cost": round(cost, 6),
            "breakdown": {
                "daily": daily_breakdown,
                "by_model": model_breakdown
            }
        }
        
        self._cache[cache_key] = result
        self._cache_expiry[cache_key] = time.time() + 300  # Cache for 5 minutes
        
        return result
    
    def get_user_summary(self, user_id: str, days: int = 30) -> Dict:
        """Get usage summary for a specific user"""
        cache_key = f"user_{user_id}_{days}"
        
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Calculate user totals for specified period
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        c.execute('''
            SELECT 
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM usage
            WHERE user_id = ? AND timestamp >= ?
        ''', (user_id, cutoff_date))
        
        row = c.fetchone()
        requests = row[0] or 0
        tokens = row[1] or 0
        cost = row[2] or 0.0
        
        # Get daily breakdown
        c.execute('''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM usage
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
        ''', (user_id, cutoff_date))
        
        daily_breakdown = []
        for row in c.fetchall():
            daily_breakdown.append({
                "date": row[0],
                "requests": row[1],
                "tokens": row[2],
                "cost": row[3]
            })
        
        # Get model breakdown
        c.execute('''
            SELECT 
                model,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM usage
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY model
            ORDER BY cost DESC
        ''', (user_id, cutoff_date))
        
        model_breakdown = []
        for row in c.fetchall():
            model_breakdown.append({
                "model": row[0],
                "requests": row[1],
                "tokens": row[2],
                "cost": row[3]
            })
        
        conn.close()
        
        result = {
            "user_id": user_id,
            "period_days": days,
            "requests": requests,
            "tokens": tokens,
            "cost": round(cost, 6),
            "average_daily_cost": round(cost / days, 6) if days > 0 else 0,
            "breakdown": {
                "daily": daily_breakdown,
                "by_model": model_breakdown
            }
        }
        
        self._cache[cache_key] = result
        self._cache_expiry[cache_key] = time.time() + 60  # Cache for 1 minute
        
        return result
    
    def get_cost_forecast(self, days: int = 30) -> Dict:
        """Forecast future costs based on recent usage patterns"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get recent daily averages
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        c.execute('''
            SELECT 
                AVG(total_cost) as avg_daily_cost,
                AVG(total_tokens) as avg_daily_tokens,
                COUNT(DISTINCT DATE(timestamp)) as days_with_data
            FROM usage
            WHERE timestamp >= ?
        ''', (cutcutoff_date,))
        
        row = c.fetchone()
        avg_daily_cost = row[0] or 0
        avg_daily_tokens = row[1] or 0
        days_with_data = row[2] or 1
        
        # Calculate monthly forecast
        days_in_month = 30
        monthly_forecast = avg_daily_cost * days_in_month
        
        # Calculate trend (comparing last 7 days vs previous 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        two_weeks_ago = (datetime.now() - timedelta(days=14)).isoformat()
        
        c.execute('''
            SELECT 
                SUM(total_cost) as cost
            FROM usage
            WHERE timestamp >= ? AND timestamp < ?
        ''', (week_ago, datetime.now().isoformat()))
        
        last_week_cost = c.fetchone()[0] or 0
        
        c.execute('''
            SELECT 
                SUM(total_cost) as cost
            FROM usage
            WHERE timestamp >= ? AND timestamp < ?
        ''', (two_weeks_ago, week_ago))
        
        previous_week_cost = c.fetchone()[0] or 0
        
        # Calculate trend percentage
        trend_percentage = 0
        if previous_week_cost > 0:
            trend_percentage = ((last_week_cost - previous_week_cost) / previous_week_cost) * 100
        
        conn.close()
        
        return {
            "forecast": {
                "daily_average": round(avg_daily_cost, 6),
                "monthly_forecast": round(monthly_forecast, 6),
                "tokens_per_day": round(avg_daily_tokens, 0)
            },
            "trend": {
                "last_week_cost": round(last_week_cost, 6),
                "previous_week_cost": round(previous_week_cost, 6),
                "percentage_change": round(trend_percentage, 2),
                "direction": "up" if trend_percentage > 0 else "down"
            },
            "based_on_days": days_with_data
        }
    
    def export_usage_data(self, start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> List[Dict]:
        """Export usage data for specified date range"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = "SELECT * FROM usage WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        c.execute(query, params)
        rows = c.fetchall()
        
        data = []
        for row in rows:
            item = dict(row)
            # Parse metadata JSON
            if item.get("metadata"):
                try:
                    item["metadata"] = json.loads(item["metadata"])
                except:
                    pass
            data.append(item)
        
        conn.close()
        return data
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self._cache:
            return False
        
        expiry = self._cache_expiry.get(cache_key, 0)
        return time.time() < expiry
    
    def _invalidate_cache(self):
        """Invalidate all cache entries"""
        self._cache.clear()
        self._cache_expiry.clear()
    
    def get_stats(self) -> Dict:
        """Get overall statistics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Total stats
        c.execute('SELECT COUNT(*), SUM(total_tokens), SUM(total_cost) FROM usage')
        total_requests, total_tokens, total_cost = c.fetchone()
        
        # Most used model
        c.execute('''
            SELECT model, COUNT(*), SUM(total_cost)
            FROM usage
            GROUP BY model
            ORDER BY SUM(total_cost) DESC
            LIMIT 1
        ''')
        top_model = c.fetchone()
        
        # Most expensive day
        c.execute('''
            SELECT date, total_cost
            FROM daily_summary
            ORDER BY total_cost DESC
            LIMIT 1
        ''')
        most_expensive_day = c.fetchone()
        
        # Recent activity (last 24 hours)
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        c.execute('''
            SELECT COUNT(*), SUM(total_cost)
            FROM usage
            WHERE timestamp >= ?
        ''', (yesterday,))
        recent_activity = c.fetchone()
        
        conn.close()
        
        return {
            "totals": {
                "requests": total_requests or 0,
                "tokens": total_tokens or 0,
                "cost": round(total_cost or 0, 6)
            },
            "top_model": {
                "name": top_model[0] if top_model else "N/A",
                "requests": top_model[1] if top_model else 0,
                "cost": round(top_model[2] or 0, 6) if top_model else 0
            },
            "most_expensive_day": {
                "date": most_expensive_day[0] if most_expensive_day else "N/A",
                "cost": round(most_expensive_day[1] or 0, 6) if most_expensive_day else 0
            },
            "recent_activity_24h": {
                "requests": recent_activity[0] or 0,
                "cost": round(recent_activity[1] or 0, 6)
            },
            "database_size_mb": self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0
        }