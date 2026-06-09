"""
Vector Store - Hierarchical storage for group watch history.

Architecture:
- Movie Knowledge Base: ChromaDB for persistent movie metadata storage
- Watch History: ChromaDB for persistent historical decision records
- Temporary Preferences: In-memory for single negotiation session

MVP Fallback: In-memory dict when chromadb is not installed.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from src.models.schemas import PreferenceVector, Movie, ConsensusResult


class WatchRecord:
    """A single group watch record."""
    def __init__(
        self,
        movie_id: str,
        title: str,
        genres: List[str],
        duration: int,
        group_score: float,
        user_scores: dict[str, float],
        preferences: List[PreferenceVector],
        timestamp: str = "",
    ):
        self.movie_id = movie_id
        self.title = title
        self.genres = genres
        self.duration = duration
        self.group_score = group_score
        self.user_scores = user_scores
        self.preferences = preferences
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_text(self) -> str:
        """Convert to text for embedding."""
        pref_texts = []
        for p in self.preferences:
            pref_texts.append(f"{p.user_name}想要{'/'.join(p.genres)}最长{p.max_duration}分钟")
        return (
            f"影片《{self.title}》类型{'/'.join(self.genres)}时长{self.duration}分钟 "
            f"群体满意度{self.group_score}分 "
            f"用户偏好：{'；'.join(pref_texts)}"
        )

    def to_dict(self) -> dict:
        return {
            "movie_id": self.movie_id,
            "title": self.title,
            "genres": ",".join(self.genres),  # Convert list to string
            "duration": self.duration,
            "group_score": self.group_score,
            "user_scores": ",".join([f"{k}:{v}" for k, v in self.user_scores.items()]),  # Convert dict to string
            "preferences": ",".join([
                f"{p.user_name}:{','.join(p.genres)}:{p.max_duration}"
                for p in self.preferences
            ]),  # Convert list to string
            "timestamp": self.timestamp,
        }


class BaseVectorStore:
    """Abstract base for vector storage."""

    def add_watch_record(self, result: ConsensusResult, preferences: List[PreferenceVector]) -> None:
        pass

    def query_similar(self, preferences: List[PreferenceVector], n_results: int = 3) -> List[dict]:
        return []

    def get_stats(self) -> dict:
        return {"total_records": 0, "provider": "none"}


class ChromaVectorStore(BaseVectorStore):
    """
    ChromaDB vector store for group watch history.
    Requires: pip install chromadb
    """

    COLLECTION_NAME = "watch_history"

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self._collection = None
        self._client = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        """Initialize Chroma client."""
        try:
            import chromadb
            os.makedirs(self.persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        except ImportError:
            self._client = None
            self._collection = None

    def is_available(self) -> bool:
        return self._collection is not None

    def add_watch_record(self, result: ConsensusResult, preferences: List[PreferenceVector]) -> None:
        """Add a watch record to vector store."""
        if not self.is_available():
            return

        record = WatchRecord(
            movie_id=result.movie.movie_id if result.movie else "unknown",
            title=result.movie.title if result.movie else "unknown",
            genres=result.movie.genres if result.movie else [],
            duration=result.movie.duration if result.movie else 0,
            group_score=result.group_score,
            user_scores={v.user_name: v.score for v in result.votes},
            preferences=preferences,
        )

        doc_id = f"watch_{record.timestamp}_{record.movie_id}"
        self._collection.add(
            ids=[doc_id],
            documents=[record.to_text()],
            metadatas=[record.to_dict()],
        )

    def query_similar(self, preferences: List[PreferenceVector], n_results: int = 3) -> List[dict]:
        """Query similar historical decisions."""
        if not self.is_available():
            return []

        # Check if collection is empty
        count = self._collection.count()
        if count == 0:
            return []

        # Build query text from current preferences
        query_parts = []
        for p in preferences:
            query_parts.append(f"{'/'.join(p.genres)}最长{p.max_duration}分钟")
        query_text = "群体想看" + "；".join(query_parts)

        results = self._collection.query(
            query_texts=[query_text],
            n_results=min(n_results, count),
        )

        records = []
        if results["metadatas"] and results["metadatas"][0]:
            for i, meta in enumerate(results["metadatas"][0]):
                dist = results["distances"][0][i] if results["distances"] else 1.0
                records.append({
                    **meta,
                    "similarity": 1.0 - float(dist),
                })
        return records

    def get_stats(self) -> dict:
        if not self.is_available():
            return {"total_records": 0, "provider": "chroma (unavailable)"}
        return {
            "total_records": self._collection.count(),
            "provider": "chroma",
            "persist_dir": self.persist_dir,
        }


class MemoryVectorStore(BaseVectorStore):
    """
    In-memory fallback when Chroma is not available.
    Simple list-based storage with keyword matching.
    """

    def __init__(self):
        self.records: List[WatchRecord] = []

    def is_available(self) -> bool:
        return True

    def add_watch_record(self, result: ConsensusResult, preferences: List[PreferenceVector]) -> None:
        record = WatchRecord(
            movie_id=result.movie.movie_id if result.movie else "unknown",
            title=result.movie.title if result.movie else "unknown",
            genres=result.movie.genres if result.movie else [],
            duration=result.movie.duration if result.movie else 0,
            group_score=result.group_score,
            user_scores={v.user_name: v.score for v in result.votes},
            preferences=preferences,
        )
        self.records.append(record)

    def query_similar(self, preferences: List[PreferenceVector], n_results: int = 3) -> List[dict]:
        """Keyword-based matching (no embeddings)."""
        current_genres = set()
        for p in preferences:
            current_genres.update(p.genres)

        scored = []
        for r in self.records:
            score = 0
            r_genres = set(r.genres)
            overlap = len(current_genres & r_genres)
            score += overlap * 2
            score += r.group_score  # higher satisfaction = better precedent
            scored.append((score, r))

        scored.sort(key=lambda x: -x[0])
        return [
            {
                **s[1].to_dict(),
                "similarity": s[0] / 10.0,
            }
            for s in scored[:n_results]
        ]

    def get_stats(self) -> dict:
        return {"total_records": len(self.records), "provider": "memory"}


def create_vector_store(persist_dir: str = "./chroma_db") -> BaseVectorStore:
    """
    Factory: Chroma (if installed) > Memory (fallback)
    """
    chroma = ChromaVectorStore(persist_dir)
    if chroma.is_available():
        print(f"  [Memory] Using Chroma vector store ({chroma.get_stats()['total_records']} records)")
        return chroma
    print(f"  [Memory] Chroma unavailable, using in-memory store")
    return MemoryVectorStore()


class HierarchicalVectorStore(BaseVectorStore):
    """
    Hierarchical storage combining:
    - ChromaDB: Persistent storage for watch history and movie knowledge base
    - Memory: Temporary storage for current negotiation session preferences
    
    Architecture:
    1. Temporary Preferences: In-memory (cleared after each negotiation)
    2. Watch History: ChromaDB (persistent across sessions)
    3. Movie Knowledge Base: ChromaDB (persistent movie metadata)
    """

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self._chroma = ChromaVectorStore(persist_dir)
        self._memory = MemoryVectorStore()
        
        # Track if chroma is available
        self._chroma_available = self._chroma.is_available()

    def is_available(self) -> bool:
        """At least one storage is always available."""
        return True

    def add_watch_record(self, result: ConsensusResult, preferences: List[PreferenceVector]) -> None:
        """
        Add watch record to both stores:
        - ChromaDB for persistent history
        - Memory for temporary session
        """
        # Add to memory (temporary)
        self._memory.add_watch_record(result, preferences)
        
        # Add to ChromaDB (persistent) if available
        if self._chroma_available:
            try:
                self._chroma.add_watch_record(result, preferences)
                print(f"  [Memory] 已记录观影历史到 ChromaDB")
            except Exception as e:
                print(f"  [Memory] ChromaDB 记录失败: {e}")

    def query_similar(self, preferences: List[PreferenceVector], n_results: int = 3) -> List[dict]:
        """
        Query similar records with fallback:
        1. First try ChromaDB (persistent history)
        2. Fallback to memory (temporary session)
        """
        results = []
        
        # First try ChromaDB for persistent history
        if self._chroma_available:
            try:
                results = self._chroma.query_similar(preferences, n_results)
                if results:
                    print(f"  [Memory] 从 ChromaDB 检索到 {len(results)} 条历史记录")
            except Exception as e:
                print(f"  [Memory] ChromaDB 查询失败: {e}")
        
        # Fallback to memory if no results from ChromaDB
        if not results:
            results = self._memory.query_similar(preferences, n_results)
            if results:
                print(f"  [Memory] 从内存检索到 {len(results)} 条记录")
        
        return results

    def get_stats(self) -> dict:
        memory_stats = self._memory.get_stats()
        if self._chroma_available:
            chroma_stats = self._chroma.get_stats()
            return {
                "total_records": memory_stats["total_records"] + chroma_stats["total_records"],
                "provider": "hierarchical",
                "chroma_records": chroma_stats["total_records"],
                "memory_records": memory_stats["total_records"],
                "persist_dir": self.persist_dir,
            }
        return {
            "total_records": memory_stats["total_records"],
            "provider": "hierarchical (chroma unavailable)",
            "memory_records": memory_stats["total_records"],
        }


def create_hierarchical_store(persist_dir: str = "./chroma_db") -> HierarchicalVectorStore:
    """
    Create hierarchical vector store:
    - ChromaDB for persistent storage (watch history, movie KB)
    - Memory for temporary storage (current session preferences)
    """
    store = HierarchicalVectorStore(persist_dir)
    stats = store.get_stats()
    print(f"  [Memory] Using Hierarchical store (Chroma: {stats.get('chroma_records', 0)} records, Memory: {stats.get('memory_records', 0)} records)")
    return store
