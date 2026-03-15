"""Embedding model wrapper for sentence-transformers."""

from __future__ import annotations


class EmbeddingModel:
    """Wrapper around sentence-transformers for embedding generation.

    Uses lazy loading — the model is loaded on first use, not on init.
    """

    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5") -> None:
        self._model_name = model_name
        self._model = None

    def _load_model(self):
        """Load the model on first use."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name, trust_remote_code=True)

    def embed(self, text: str) -> list[float]:
        """Return embedding vector for a single text."""
        self._load_model()
        vector = self._model.encode(text, convert_to_numpy=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for a batch of texts."""
        self._load_model()
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return vectors.tolist()

    def tokenize_count(self, text: str) -> int:
        """Return the number of tokens for the given text using the model's tokenizer."""
        self._load_model()
        tokenized = self._model.tokenizer.encode(text)
        return len(tokenized)
