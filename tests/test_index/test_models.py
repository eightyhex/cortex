"""Tests for the EmbeddingModel wrapper."""

import pytest

from cortex.index.models import EmbeddingModel


@pytest.fixture(scope="module")
def model():
    """Shared model instance (lazy-loaded on first use)."""
    return EmbeddingModel()


class TestEmbeddingModel:
    def test_lazy_loading(self):
        """Model should not be loaded until first use."""
        m = EmbeddingModel()
        assert m._model is None

    def test_embed_returns_list_of_floats(self, model):
        result = model.embed("hello world")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_embed_dimension(self, model):
        """Embedding should be 768-dimensional."""
        result = model.embed("test embedding dimension")
        assert len(result) == 768

    def test_embed_batch(self, model):
        texts = ["first sentence", "second sentence", "third sentence"]
        results = model.embed_batch(texts)
        assert len(results) == 3
        assert all(len(v) == 768 for v in results)

    def test_embed_batch_empty(self, model):
        results = model.embed_batch([])
        assert results == []

    def test_tokenize_count(self, model):
        count = model.tokenize_count("hello world")
        assert isinstance(count, int)
        assert count > 0

    def test_different_texts_different_embeddings(self, model):
        v1 = model.embed("the cat sat on the mat")
        v2 = model.embed("quantum computing research paper")
        # Vectors should differ for semantically different texts
        assert v1 != v2
