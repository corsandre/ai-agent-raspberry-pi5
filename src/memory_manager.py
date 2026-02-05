import chromadb
from chromadb.config import Settings
from datetime import datetime
from typing import List, Dict, Any
import json
import hashlib
import os
import sqlite3

class PersistentMemory:
    def __init__(self, chroma_host="localhost", chroma_port=8000, workspace_dir="/workspace"):
        self.client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port
        )
        
        self.workspace_dir = workspace_dir
        
        # Collections for different memory types
        self.conversations = self.client.get_or_create_collection(
            name="conversations",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.code_snippets = self.client.get_or_create_collection(
            name="code_snippets",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.project_context = self.client.get_or_create_collection(
            name="project_context",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Initialize SQLite database
        self._init_sqlite()
    
    def _init_sqlite(self):
        """Initialize SQLite database for quick access"""
        db_path = os.path.join(self.workspace_dir, 'memory.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS conversations
            (id TEXT PRIMARY KEY, query TEXT, response TEXT,
             metadata TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
        ''')
        conn.commit()
        conn.close()
    
    def store_conversation(self, query: str, response: str, metadata: Dict = None):
        """Store conversation with vector embedding"""
        conversation_id = hashlib.md5(f"{query}{datetime.now()}".encode()).hexdigest()
        
        self.conversations.add(
            documents=[f"Q: {query}\nA: {response}"],
            metadatas=[{
                "query": query,
                "response": response,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }],
            ids=[conversation_id]
        )
        
        # Also store in SQLite for quick lookup
        self._store_in_sqlite(conversation_id, query, response, metadata)
        
        return conversation_id
    
    def _store_in_sqlite(self, conversation_id, query, response, metadata):
        """Backup storage for quick access"""
        conn = sqlite3.connect(os.path.join(self.workspace_dir, 'memory.db'))
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO conversations (id, query, response, metadata)
            VALUES (?, ?, ?, ?)
        ''', (conversation_id, query, response, json.dumps(metadata or {})))
        conn.commit()
        conn.close()
    
    def retrieve_relevant_context(self, query: str, n_results: int = 5):
        """Find similar past conversations"""
        results = self.conversations.query(
            query_texts=[query],
            n_results=n_results
        )
        
        context = []
        if results['documents']:
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                context.append({
                    "content": doc,
                    "metadata": metadata,
                    "relevance_score": metadata.get("score", 0)
                })
        
        return context
    
    def search(self, query: str, limit: int = 5):
        """Search conversations (alias for retrieve_relevant_context)"""
        return self.retrieve_relevant_context(query, limit)
    
    def store_code_snippet(self, code: str, language: str, description: str):
        """Store reusable code snippets"""
        snippet_id = hashlib.md5(code.encode()).hexdigest()[:16]
        
        self.code_snippets.add(
            documents=[code],
            metadatas=[{
                "language": language,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "hash": snippet_id
            }],
            ids=[snippet_id]
        )
        
        return snippet_id