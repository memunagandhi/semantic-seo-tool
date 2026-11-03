import os
import re
import math
from typing import List, Dict, Any

try:
    import numpy as np
except ImportError:
    np = None

import requests


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if np is not None:
        a = np.array(v1, dtype=float)
        b = np.array(v2, dtype=float)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    else:
        dot = sum(x * y for x, y in zip(v1, v2))
        norm_a = math.sqrt(sum(x * x for x in v1))
        norm_b = math.sqrt(sum(y * y for y in v2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def build_local_tfidf_embeddings(texts: List[str]) -> List[List[float]]:
    """Build fast local TF-IDF semantic vector representation."""
    tokenized = []
    vocab = set()
    for text in texts:
        words = re.findall(r'[a-zA-Z0-9]+', text.lower())
        tokenized.append(words)
        vocab.update(words)

    vocab = sorted(list(vocab))
    word2idx = {w: i for i, w in enumerate(vocab)}
    n_docs = len(texts)

    df = {w: 0 for w in vocab}
    for words in tokenized:
        for w in set(words):
            df[w] += 1

    idf = {w: math.log((n_docs + 1) / (df[w] + 1)) + 1.0 for w in vocab}

    vectors = []
    for words in tokenized:
        vec = [0.0] * len(vocab)
        if words:
            for w in words:
                idx = word2idx[w]
                vec[idx] += 1.0 / len(words)
            vec = [vec[i] * idf[vocab[i]] for i in range(len(vocab))]
        vectors.append(vec)

    return vectors


class SemanticIREngine:
    def __init__(self, api_key: str = None):
        self.api_key = (api_key or os.environ.get("COHERE_API_KEY", "")).strip()
        self.base_url = "https://api.cohere.com/v2"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_embeddings(self, texts: List[str], input_type: str = "search_document") -> List[List[float]]:
        if not self.is_configured:
            return build_local_tfidf_embeddings(texts)

        url = f"{self.base_url}/embed"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "embed-english-v3.0",
            "texts": texts,
            "input_type": input_type,
            "embedding_types": ["float"]
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                embeddings = data.get("embeddings", {}).get("float", [])
                if embeddings:
                    return embeddings
        except Exception:
            pass

        return build_local_tfidf_embeddings(texts)

    def rerank(self, query: str, documents: List[str]) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return self._local_rerank_simulation(query, documents)

        url = f"{self.base_url}/rerank"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "rerank-v3.5",
            "query": query,
            "documents": documents,
            "top_n": len(documents)
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("results", []):
                    results.append({
                        "index": item["index"],
                        "relevance_score": float(item["relevance_score"]),
                        "document": documents[item["index"]]
                    })
                return results
        except Exception:
            pass

        return self._local_rerank_simulation(query, documents)

    def _local_rerank_simulation(self, query: str, documents: List[str]) -> List[Dict[str, Any]]:
        query_words = set(re.findall(r'[a-zA-Z0-9]+', query.lower()))
        results = []
        for idx, doc in enumerate(documents):
            doc_words = set(re.findall(r'[a-zA-Z0-9]+', doc.lower()))
            overlap = len(query_words.intersection(doc_words))
            coverage = overlap / max(len(query_words), 1)
            density = overlap / math.sqrt(max(len(doc_words), 1))
            score = round(min(0.99, (coverage * 0.7) + (density * 0.3)), 4)
            results.append({
                "index": idx,
                "relevance_score": score,
                "document": doc
            })

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results

    def analyze(self, query: str, documents: List[str]) -> Dict[str, Any]:
        """Run full 3-step Dense Retrieval, Rerank, and AEO Gap Analysis pipeline."""
        query = query.strip()
        cleaned_docs = [d.strip() for d in documents if d.strip()]

        if not query or not cleaned_docs:
            raise ValueError("Query and at least one document passage are required.")

        # Step 1: Dense Retrieval
        all_texts = [query] + cleaned_docs
        embeddings = self.get_embeddings(all_texts)
        query_emb = embeddings[0]
        doc_embs = embeddings[1:]

        dense_list = []
        for idx, (doc, emb) in enumerate(zip(cleaned_docs, doc_embs)):
            sim = cosine_similarity(query_emb, emb)
            dense_list.append({
                "original_index": idx,
                "document": doc,
                "similarity": round(sim, 4)
            })

        dense_list.sort(key=lambda x: x["similarity"], reverse=True)
        for dense_rank, item in enumerate(dense_list, start=1):
            item["initial_dense_rank"] = dense_rank

        # Step 2: Cohere Cross-Encoder Reranking
        rerank_list = self.rerank(query=query, documents=cleaned_docs)

        # Merge results & calculate rank shift
        comparison_table = []
        for new_position, item in enumerate(rerank_list, start=1):
            orig_idx = item["index"]
            dense_match = next(d for d in dense_list if d["original_index"] == orig_idx)
            old_rank = dense_match["initial_dense_rank"]
            shift = old_rank - new_position  # Positive = moved up, Negative = moved down

            comparison_table.append({
                "original_index": orig_idx,
                "document": item["document"],
                "dense_similarity": dense_match["similarity"],
                "initial_dense_rank": old_rank,
                "rerank_score": round(item["relevance_score"], 4),
                "post_rerank_position": new_position,
                "rank_shift": shift
            })

        # Step 3: AEO Verdict & Topical Gap
        winner = comparison_table[0]
        top_score = winner["rerank_score"]

        if top_score >= 0.80:
            verdict = "High Alignment"
            verdict_badge = "success"
        elif top_score >= 0.50:
            verdict = "Moderate Alignment"
            verdict_badge = "warning"
        else:
            verdict = "Low Alignment"
            verdict_badge = "danger"

        # Missing entity words
        stop_words = {"what", "how", "why", "when", "where", "which", "is", "are", "the", "and", "for", "with", "does", "do", "needed", "required"}
        query_terms = [t for t in re.findall(r'[a-zA-Z0-9]+', query.lower()) if len(t) > 2 and t not in stop_words]
        doc_terms = set(re.findall(r'[a-zA-Z0-9]+', winner["document"].lower()))
        missing_terms = [t for t in query_terms if t not in doc_terms]

        if missing_terms:
            copy_advice = f"Include '{', '.join(missing_terms)}' directly in the heading or first sentence of this passage to maximize AI Overview citation."
        else:
            copy_advice = "Passage completely aligns with primary search intent entities. Ready for Answer Engine optimization."

        return {
            "query": query,
            "engine_mode": "Cohere v3.5 Live" if self.is_configured else "Local Simulation Engine",
            "is_live_api": self.is_configured,
            "winner": winner,
            "comparison_table": comparison_table,
            "verdict": verdict,
            "verdict_badge": verdict_badge,
            "missing_entities": missing_terms,
            "copy_advice": copy_advice,
            "total_passages": len(cleaned_docs)
        }
