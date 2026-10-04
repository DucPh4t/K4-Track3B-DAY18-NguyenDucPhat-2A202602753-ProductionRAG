from __future__ import annotations

"""Module 2: Hybrid Search — BM25 (Vietnamese) + Dense + RRF."""

import os, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME, EMBEDDING_MODEL,
                    EMBEDDING_DIM, BM25_TOP_K, DENSE_TOP_K, HYBRID_TOP_K)


@dataclass
class SearchResult:
    text: str
    score: float
    metadata: dict
    method: str  # "bm25", "dense", "hybrid"


def segment_vietnamese(text: str) -> str:
    """Segment Vietnamese text into words.

    underthesea nối từ ghép bằng "_" (VD: "nghỉ_phép").
    BM25 tokenize bằng split(" ") nên replace("_", " ") để query và corpus khớp tốt.
    """
    try:
        from underthesea import word_tokenize
        segmented = word_tokenize(text, format="text")
        return segmented.replace("_", " ")
    except Exception:
        return text


class BM25Search:
    def __init__(self):
        self.corpus_tokens = []
        self.documents = []
        self.bm25 = None

    def index(self, chunks: list[dict]) -> None:
        """Build BM25 index from chunks."""
        self.documents = chunks
        self.corpus_tokens = [segment_vietnamese(c.get("text", "")).lower().split() for c in chunks]
        from rank_bm25 import BM25Okapi
        if self.corpus_tokens:
            self.bm25 = BM25Okapi(self.corpus_tokens)

    def search(self, query: str, top_k: int = BM25_TOP_K) -> list[SearchResult]:
        """Search using BM25."""
        if self.bm25 is None or not self.documents:
            return []
        tokenized_query = segment_vietnamese(query).lower().split()
        if not tokenized_query:
            return []
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for i in top_indices:
            if scores[i] > 0:
                results.append(SearchResult(
                    text=self.documents[i]["text"],
                    score=float(scores[i]),
                    metadata=self.documents[i].get("metadata", {}),
                    method="bm25"
                ))
        return results


_CACHED_ENCODERS: dict = {}


class DenseSearch:
    def __init__(self):
        from qdrant_client import QdrantClient
        try:
            self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=2)
            self.client.get_collections()
        except Exception:
            self.client = QdrantClient(":memory:")
        self._encoder = None

    def _get_encoder(self):
        if self._encoder is None:
            if EMBEDDING_MODEL not in _CACHED_ENCODERS:
                from sentence_transformers import SentenceTransformer
                try:
                    _CACHED_ENCODERS[EMBEDDING_MODEL] = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
                except Exception:
                    try:
                        _CACHED_ENCODERS[EMBEDDING_MODEL] = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                    except Exception:
                        _CACHED_ENCODERS[EMBEDDING_MODEL] = SentenceTransformer(EMBEDDING_MODEL)
            self._encoder = _CACHED_ENCODERS[EMBEDDING_MODEL]
        return self._encoder

    def index(self, chunks: list[dict], collection: str = COLLECTION_NAME) -> None:
        """Index chunks into Qdrant."""
        from qdrant_client.models import Distance, VectorParams, PointStruct

        dim = self._get_encoder().get_sentence_embedding_dimension()
        self.client.recreate_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )
        if not chunks:
            return

        texts = [c["text"] for c in chunks]
        vectors = self._get_encoder().encode(texts, show_progress_bar=False)
        points = [
            PointStruct(
                id=i,
                vector=vectors[i].tolist(),
                payload={**chunks[i].get("metadata", {}), "text": chunks[i]["text"]}
            )
            for i in range(len(chunks))
        ]
        self.client.upsert(collection_name=collection, points=points)

    def search(self, query: str, top_k: int = DENSE_TOP_K, collection: str = COLLECTION_NAME) -> list[SearchResult]:
        """Search using dense vectors."""
        query_vector = self._get_encoder().encode(query).tolist()

        try:
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(collection_name=collection, query=query_vector, limit=top_k)
                points = response.points
            else:
                points = self.client.search(collection_name=collection, query_vector=query_vector, limit=top_k)
        except Exception:
            points = []

        return [
            SearchResult(
                text=pt.payload.get("text", ""),
                score=float(pt.score),
                metadata=pt.payload,
                method="dense"
            )
            for pt in points
        ]


def reciprocal_rank_fusion(results_list: list[list[SearchResult]], k: int = 60,
                           top_k: int = HYBRID_TOP_K) -> list[SearchResult]:
    """Merge ranked lists using RRF: score(d) = Σ 1/(k + rank + 1)."""
    rrf_scores: dict[str, dict] = {}
    for r_list in results_list:
        for rank, res in enumerate(r_list):
            if res.text not in rrf_scores:
                rrf_scores[res.text] = {"score": 0.0, "result": res}
            rrf_scores[res.text]["score"] += 1.0 / (k + rank + 1)

    sorted_candidates = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)[:top_k]
    return [
        SearchResult(
            text=cand["result"].text,
            score=float(cand["score"]),
            metadata=cand["result"].metadata,
            method="hybrid"
        )
        for cand in sorted_candidates
    ]


class HybridSearch:
    """Combines BM25 + Dense + RRF. (Đã implement sẵn — dùng classes ở trên)"""
    def __init__(self):
        self.bm25 = BM25Search()
        self.dense = DenseSearch()

    def index(self, chunks: list[dict]) -> None:
        self.bm25.index(chunks)
        self.dense.index(chunks)

    def search(self, query: str, top_k: int = HYBRID_TOP_K) -> list[SearchResult]:
        bm25_results = self.bm25.search(query, top_k=BM25_TOP_K)
        dense_results = self.dense.search(query, top_k=DENSE_TOP_K)
        return reciprocal_rank_fusion([bm25_results, dense_results], top_k=top_k)


if __name__ == "__main__":
    print(f"Original:  Nhân viên được nghỉ phép năm")
    print(f"Segmented: {segment_vietnamese('Nhân viên được nghỉ phép năm')}")
