"""
Memory Manager with ChromaDB integration
"""
import chromadb
from chromadb.config import Settings
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import hashlib
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class PersistentMemory:
    def __init__(self, chroma_host: str = "localhost", chroma_port: int = 8000, workspace_dir: str = "/workspace"):
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.workspace_dir = workspace_dir
        
        # Initialize ChromaDB client
        self.client = chromadb.HttpClient(
            host=self.chroma_host,
            port=self.chroma_port,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
                chroma_client_auth_credentials=""
            )
        )
        
        # Initialize collections
        self.conversations = self._get_or_create_collection("conversations")
        self.code_snippets = self._get_or_create_collection("code_snippets")
        self.projects = self._get_or_create_collection("projects")
        
        # SQLite for metadata (optional, for faster lookups)
        self._init_sqlite()
        
        logger.info(f"Memory manager initialized. Collections: {self.client.list_collections()}")
    
    def _get_or_create_collection(self, name: str):
        """Get existing collection or create new one"""
        try:
            return self.client.get_collection(name)
        except:
            return self.client.create_collection(
                name=name,
                metadata={"description": f"{name} collection", "created": datetime.now().isoformat()}
            )
    
    def _init_sqlite(self):
        """Initialize SQLite for metadata storage"""
        import sqlite3
        self.sqlite_path = Path(self.workspace_dir) / "memory.db"
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.sqlite_path)
        c = conn.cursor()
        
        # Create tables
        c.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                query TEXT,
                response TEXT,
                model TEXT,
                timestamp DATETIME,
                project TEXT,
                tokens_used INTEGER,
                metadata TEXT
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS code_snippets (
                id TEXT PRIMARY KEY,
                code TEXT,
                language TEXT,
                description TEXT,
                tags TEXT,
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME,
                last_used DATETIME
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                path TEXT,
                created_at DATETIME,
                last_accessed DATETIME,
                metadata TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_conversation(self, query: str, response: str, model: str, 
                          project: Optional[str] = None, tokens_used: int = 0,
                          metadata: Dict = None) -> str:
        """Store a conversation in memory"""
        # Generate unique ID
        conversation_id = hashlib.md5(
            f"{query}{response}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Store in ChromaDB
        self.conversations.add(
            documents=[f"Q: {query}\nA: {response}"],
            metadatas=[{
                "query": query[:500],  # Truncate long queries
                "response": response[:1000],  # Truncate long responses
                "model": model,
                "project": project or "default",
                "timestamp": datetime.now().isoformat(),
                "tokens_used": tokens_used,
                "type": "conversation"
            }],
            ids=[conversation_id]
        )
        
        # Store in SQLite
        import sqlite3
        conn = sqlite3.connect(self.sqlite_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO conversations (id, query, response, model, timestamp, project, tokens_used, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            conversation_id,
            query,
            response,
            model,
            datetime.now().isoformat(),
            project,
            tokens_used,
            json.dumps(metadata or {})
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored conversation {conversation_id} for project: {project}")
        return conversation_id
    
    def retrieve_relevant_context(self, query: str, n_results: int = 5, 
                                 project: Optional[str] = None) -> List[Dict]:
        """Retrieve relevant past conversations"""
        try:
            # Build filter
            where_filter = {}
            if project:
                where_filter = {"project": project}
            
            # Query ChromaDB
            results = self.conversations.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            
            context = []
            if results and results['documents']:
                for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
                    context.append({
                        "id": results['ids'][0][i],
                        "content": doc,
                        "metadata": metadata,
                        "distance": results['distances'][0][i] if results['distances'] else 0
                    })
            
            return context
        
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []
    
    def store_code_snippet(self, code: str, language: str, description: str, 
                          tags: List[str] = None) -> str:
        """Store a code snippet for future reuse"""
        snippet_id = hashlib.md5(code.encode()).hexdigest()[:16]
        
        # Store in ChromaDB
        self.code_snippets.add(
            documents=[code],
            metadatas=[{
                "language": language,
                "description": description,
                "tags": ",".join(tags or []),
                "created_at": datetime.now().isoformat(),
                "type": "code_snippet"
            }],
            ids=[snippet_id]
        )
        
        # Store in SQLite
        import sqlite3
        conn = sqlite3.connect(self.sqlite_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT OR REPLACE INTO code_snippets 
            (id, code, language, description, tags, created_at, last_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            snippet_id,
            code,
            language,
            description,
            ",".join(tags or []),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored code snippet {snippet_id}: {description}")
        return snippet_id
    
    def search_code_snippets(self, query: str, language: Optional[str] = None, 
                            limit: int = 10) -> List[Dict]:
        """Search for relevant code snippets"""
        try:
            where_filter = {}
            if language:
                where_filter = {"language": language}
            
            results = self.code_snippets.query(
                query_texts=[query],
                n_results=limit,
                where=where_filter
            )
            
            snippets = []
            if results and results['documents']:
                for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
                    snippets.append({
                        "id": results['ids'][0][i],
                        "code": doc,
                        "language": metadata.get("language", "unknown"),
                        "description": metadata.get("description", ""),
                        "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                        "created_at": metadata.get("created_at")
                    })
            
            return snippets
        
        except Exception as e:
            logger.error(f"Error searching code snippets: {e}")
            return []
    
    def create_project(self, name: str, description: str = "", path: str = None):
        """Create or update a project context"""
        project_id = hashlib.md5(name.encode()).hexdigest()[:16]
        
        if not path:
            path = str(Path(self.workspace_dir) / name)
        
        # Store in ChromaDB
        self.projects.add(
            documents=[description],
            metadatas=[{
                "name": name,
                "path": path,
                "created_at": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
                "type": "project"
            }],
            ids=[project_id]
        )
        
        # Store in SQLite
        import sqlite3
        conn = sqlite3.connect(self.sqlite_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT OR REPLACE INTO projects (id, name, description, path, created_at, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            project_id,
            name,
            description,
            path,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # Create project directory
        Path(path).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created project {project_id}: {name}")
        return project_id
    
    def get_project_context(self, project_name: str, limit: int = 20) -> List[Dict]:
        """Get all conversations and code for a project"""
        try:
            # Get conversations for this project
            conv_results = self.conversations.query(
                query_texts=[""],
                n_results=limit,
                where={"project": project_name}
            )
            
            # Get code snippets
            code_results = self.code_snippets.query(
                query_texts=[""],
                n_results=limit
            )
            
            context = []
            
            # Add conversations
            if conv_results and conv_results['documents']:
                for i, doc in enumerate(conv_results['documents'][0]):
                    context.append({
                        "type": "conversation",
                        "content": doc,
                        "metadata": conv_results['metadatas'][0][i]
                    })
            
            # Add code snippets
            if code_results and code_results['documents']:
                for i, doc in enumerate(code_results['documents'][0]):
                    context.append({
                        "type": "code_snippet",
                        "content": doc,
                        "metadata": code_results['metadatas'][0][i]
                    })
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting project context: {e}")
            return []
    
    def cleanup_old_conversations(self, days_old: int = 30):
        """Clean up conversations older than specified days"""
        import sqlite3
        from datetime import datetime, timedelta
        
        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
        
        conn = sqlite3.connect(self.sqlite_path)
        c = conn.cursor()
        
        # Get IDs to delete
        c.execute('''
            SELECT id FROM conversations 
            WHERE timestamp < ?
        ''', (cutoff_date,))
        
        old_ids = [row[0] for row in c.fetchall()]
        
        # Delete from SQLite
        c.execute('''
            DELETE FROM conversations 
            WHERE timestamp < ?
        ''', (cutoff_date,))
        
        conn.commit()
        conn.close()
        
        # Delete from ChromaDB
        if old_ids:
            self.conversations.delete(ids=old_ids)
        
        logger.info(f"Cleaned up {len(old_ids)} old conversations")
        return len(old_ids)
    
    def get_stats(self) -> Dict:
        """Get memory statistics"""
        import sqlite3
        
        conn = sqlite3.connect(self.sqlite_path)
        c = conn.cursor()
        
        stats = {
            "conversations": 0,
            "code_snippets": 0,
            "projects": 0,
            "total_size_mb": 0
        }
        
        # Count conversations
        c.execute('SELECT COUNT(*) FROM conversations')
        stats["conversations"] = c.fetchone()[0]
        
        # Count code snippets
        c.execute('SELECT COUNT(*) FROM code_snippets')
        stats["code_snippets"] = c.fetchone()[0]
        
        # Count projects
        c.execute('SELECT COUNT(*) FROM projects')
        stats["projects"] = c.fetchone()[0]
        
        conn.close()
        
        # Calculate size
        if self.sqlite_path.exists():
            stats["total_size_mb"] = self.sqlite_path.stat().st_size / (1024 * 1024)
        
        # Add collection counts
        try:
            stats["chroma_collections"] = len(self.client.list_collections())
        except:
            stats["chroma_collections"] = 0
        
        return stats