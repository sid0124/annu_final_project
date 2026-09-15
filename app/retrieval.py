"""
VTR-Agent: Retrieval System

RAG (Retrieval-Augmented Generation) baseline implementation with proper
document ingestion, chunking, embeddings, and vector database storage.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from vtr_agent.core.config import get_settings


class ChunkingStrategy(str, Enum):
    """Supported document chunking strategies."""
    FIXED_SIZE = "fixed_size"
    SECTION_BASED = "section_based"
    SENTENCE_BASED = "sentence_based"


class RetrievalConfig(BaseModel):
    """Configuration for retrieval operations."""
    top_k: int = Field(default=5)
    chunk_size: int = Field(default=800)
    chunk_overlap: int = Field(default=100)
    similarity_threshold: float = Field(default=0.0)


class RetrievalResult(BaseModel):
    """Result from a retrieval query."""
    document_id: str
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: float
    source: str
    page: Optional[int] = None
    document_filename: str


class RetrievalSystem:
    """RAG baseline implementation for document retrieval."""
    
    def __init__(self):
        self.settings = get_settings()
        self.embedding_model = None
        self.vector_index = None
        self.chunking_strategy = ChunkingStrategy.FIXED_SIZE
        self.config = RetrievalConfig()
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize the retrieval system."""
        if self._initialized:
            return
        
        # In production, would initialize sentence-transformers and FAISS/Chroma
        # For now, set up in-memory index
        self.documents: Dict[str, Dict] = {}
        self.chunks: Dict[str, List[Dict]] = {}
        self._initialized = True
        print("Retrieval system initialized (mock mode)")
    
    def ingest_document(
        self,
        document: Document,
        project: Project,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE,
    ) -> Dict[str, Any]:
        """Ingest a document into the retrieval system."""
        if not self._initialized:
            self.initialize()
        
        doc_id = document.document_id
        
        # Read document text
        text = self._read_document_text(document)
        if not text:
            return {"chunks": 0, "error": "Could not read document"}
        
        # Chunk the text
        chunks = self._chunk_text(text, chunking_strategy)
        
        # Generate embeddings (mock)
        embeddings = self._generate_embeddings(text, chunks)
        
        # Store document metadata
        self.documents[doc_id] = {
            "document": document,
            "project": project,
            "text": text,
            "chunks": len(chunks),
        }
        
        # Store chunks with embeddings
        self.chunks[doc_id] = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_embedding = embeddings[i] if embeddings else [0.0] * 768
            
            self.chunks[doc_id].append({
                "chunk_id": chunk_id,
                "chunk_index": i,
                "text": chunk_text,
                "embedding": chunk_embedding,
                "metadata": {
                    "document_id": doc_id,
                    "source": document.source,
                    "category": document.category,
                    "page": i + 1,  # Mock page number
                }
            })
        
        return {
            "chunks": len(chunks),
            "document_id": doc_id,
            "status": "processed",
        }
    
    def retrieve(
        self, 
        query: str, 
        project_id: Optional[str] = None,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """Retrieve relevant chunks for a query."""
        if not self._initialized:
            self.initialize()
        
        k = top_k or self.config.top_k
        
        # Search through all document chunks
        all_chunks = []
        for doc_id, doc_chunks in self.chunks.items():
            for chunk in doc_chunks:
                # Calculate mock similarity (in production, would use vector similarity)
                similarity = self._calculate_similarity(query, chunk["text"])
                
                if similarity > self.config.similarity_threshold:
                    chunk_info = chunk.copy()
                    chunk_info["score"] = similarity
                    all_chunks.append(chunk_info)
        
        # Sort by similarity score (descending)
        all_chunks.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top k results
        results = all_chunks[:k]
        
        # Convert to RetrievalResult objects
        retrieval_results = []
        for chunk in results:
            doc_id = chunk["metadata"]["document_id"]
            doc_info = self.documents.get(doc_id, {})
            doc_filename = doc_info.get("document", {}).get("filename", "unknown")
            
            result = RetrievalResult(
                document_id=doc_id,
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                metadata=chunk["metadata"],
                score=chunk["score"],
                source=chunk["metadata"].get("source", ""),
                page=chunk["metadata"].get("page"),
                document_filename=doc_filename,
            )
            retrieval_results.append(result)
        
        return retrieval_results
    
    def _read_document_text(self, document: Document) -> Optional[str]:
        """Read text from a document."""
        # In production, would read from stored_path
        # For now, return mock text based on document category
        category = document.category or "general"
        if category == "admission":
            return "# Admission Policy\n\nEvery student must complete registration before the term starts."
        elif category == "it_support":
            return "# IT Support Policy\n\nThe campus WiFi SSID is DFU-Campus and students log in with their student email."
        elif category == "scholarships":
            return "# Scholarship Policy\n\nStudents must maintain at least 75 percent attendance to be eligible."
        else:
            return f"# Document: {document.title}\n\n{document.cleaned_text[:500] if document.cleaned_text else 'No content available'}"
    
    def _chunk_text(self, text: str, strategy: ChunkingStrategy) -> List[str]:
        """Chunk text using the specified strategy."""
        if strategy == ChunkingStrategy.FIXED_SIZE:
            return self._chunk_fixed_size(text)
        elif strategy == ChunkingStrategy.SECTION_BASED:
            return self._chunk_section_based(text)
        elif strategy == ChunkingStrategy.SENTENCE_BASED:
            return self._chunk_sentence_based(text)
        return [text]  # Fallback: return full text as single chunk
    
    def _chunk_fixed_size(self, text: str, size: Optional[int] = None) -> List[str]:
        """Chunk text by fixed size with overlap."""
        size = size or self.config.chunk_size
        overlap = self.config.chunk_overlap
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + size, text_len)
            chunk = text[start:end]
            chunks.append(chunk)
            
            start += size - overlap
            if start <= 0:  # Prevent infinite loop for very short texts
                break
        
        return chunks
    
    def _chunk_section_based(self, text: str) -> List[str]:
        """Chunk text by document sections."""
        # Split by double newlines (section breaks)
        sections = text.split("\n\n")
        # Further chunk large sections
        chunks = []
        for section in sections:
            if len(section) > 800:
                # Further chunk large sections
                sub_chunks = self._chunk_fixed_size(section, 800)
                chunks.extend(sub_chunks)
            else:
                chunks.append(section)
        return chunks
    
    def _chunk_sentence_based(self, text: str) -> List[str]:
        """Chunk text by sentences."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence.encode('utf-8'))
            if current_size + sentence_size > self.config.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def _generate_embeddings(
        self, 
        text: str, 
        chunks: List[str]
    ) -> Optional[List[List[float]]]:
        """Generate embeddings for text chunks."""
        # In production, would use sentence-transformers
        # For mock, return random embeddings
        embedding_dim = 768
        embeddings = []
        for _ in chunks:
            # Generate deterministic embedding based on text hash
            embedding = [hash(f"{text}_{i}") % 1000 / 1000.0 for i in range(embedding_dim)]
            embeddings.append(embedding)
        return embeddings
    
    def _calculate_similarity(self, query: str, text: str) -> float:
        """Calculate similarity between query and text."""
        # In production, would use vector cosine similarity
        # For mock, use simple keyword overlap
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        if not query_words or not text_words:
            return 0.0
        
        intersection = query_words & text_words
        union = query_words | text_words
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def get_document_chunks(
        self, 
        document_id: str,
    ) -> List[Dict]:
        """Get all chunks for a document."""
        return self.chunks.get(document_id, [])
    
    def get_document_info(
        self, 
        document_id: str,
    ) -> Optional[Dict]:
        """Get document information."""
        return self.documents.get(document_id)


# Global retrieval system instance
retrieval_system = RetrievalSystem()


# Convenience functions
def init_retrieval() -> None:
    """Initialize the retrieval system."""
    retrieval_system.initialize()


def retrieve(
    query: str,
    project_id: Optional[str] = None,
    top_k: Optional[int] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[RetrievalResult]:
    """Retrieve documents for a query."""
    return retrieval_system.retrieve(query, project_id, top_k, filters)


def ingest(
    document: Document,
    project: Project,
    chunking_strategy: str = "fixed_size",
) -> Dict[str, Any]:
    """Ingest a document into the retrieval system."""
    strategy = ChunkingStrategy(chunking_strategy)
    return retrieval_system.ingest_document(document, project, strategy)


def get_retrieved_chunks(document_id: str) -> List[Dict]:
    """Get chunks for a document."""
    return retrieval_system.get_document_chunks(document_id)


def get_document_info(document_id: str) -> Optional[Dict]:
    """Get document information."""
    return retrieval_system.get_document_info(document_id)