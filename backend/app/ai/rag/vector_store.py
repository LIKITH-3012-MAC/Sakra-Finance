import math
import re
from typing import Dict, List, Tuple

class LocalVectorStore:
    """
    Lightweight, pure-Python TF-IDF Vector Space Model for document retrieval.
    Provides fast, zero-dependency cosine-similarity text search for RAG context injection.
    """
    
    def __init__(self):
        self.documents: List[Dict[str, str]] = []
        self.vocabulary: Set[str] = set()
        self.df: Dict[str, int] = {}
        self.doc_vectors: List[Dict[str, float]] = []

    def _tokenize(self, text: str) -> List[str]:
        """Normalize text and split into alphabetic tokens."""
        return re.findall(r'[a-zA-Z0-9]+', text.lower())

    def add_document(self, doc_id: str, text: str, metadata: dict = None):
        """Index a document with associated text and optional metadata."""
        tokens = self._tokenize(text)
        if not tokens:
            return
        
        doc = {
            "id": doc_id,
            "text": text,
            "metadata": metadata or {},
            "tokens": tokens
        }
        self.documents.append(doc)
        
        # Update vocab and document frequencies
        unique_tokens = set(tokens)
        for token in unique_tokens:
            self.df[token] = self.df.get(token, 0) + 1
        self.vocabulary.update(unique_tokens)
        
        self._recalculate_vectors()

    def _recalculate_vectors(self):
        """Compute TF-IDF weight vectors for all indexed documents."""
        N = len(self.documents)
        self.doc_vectors = []
        
        for doc in self.documents:
            tf = {}
            for token in doc["tokens"]:
                tf[token] = tf.get(token, 0) + 1
            
            vector = {}
            for token, count in tf.items():
                idf = math.log((1 + N) / (1 + self.df.get(token, 0))) + 1
                vector[token] = count * idf
            
            # Normalize vector
            length = math.sqrt(sum(val ** 2 for val in vector.values()))
            if length > 0:
                vector = {token: val / length for token, val in vector.items()}
            
            self.doc_vectors.append(vector)

    def search(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, any], float]]:
        """Retrieve top k matches using Cosine Similarity."""
        query_tokens = self._tokenize(query)
        if not query_tokens or not self.documents:
            return []

        N = len(self.documents)
        query_tf = {}
        for token in query_tokens:
            query_tf[token] = query_tf.get(token, 0) + 1

        # Calculate query vector weights
        query_vector = {}
        for token, count in query_tf.items():
            if token in self.vocabulary:
                idf = math.log((1 + N) / (1 + self.df.get(token, 0))) + 1
                query_vector[token] = count * idf
                
        q_len = math.sqrt(sum(val ** 2 for val in query_vector.values()))
        if q_len > 0:
            query_vector = {token: val / q_len for token, val in query_vector.items()}

        results = []
        for idx, doc_vector in enumerate(self.doc_vectors):
            # Compute Dot Product of normalized query and document vectors
            score = sum(query_vector[token] * doc_vector.get(token, 0) for token in query_vector if token in doc_vector)
            if score > 0.05:  # Relevance threshold
                results.append((self.documents[idx], score))
                
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

# Global singleton store instance for in-memory session documents
vector_store = LocalVectorStore()
