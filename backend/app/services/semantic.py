"""Semantic matching tier (Phase 13e).

The capability detector's lexical word-bag matcher misses wording drift
("send out the weekly summary report" vs capability `dispatch_report`).
When an embedding service is configured (`ABSURD_EMBEDDINGS_BASE_URL`,
`ABSURD_EMBEDDINGS_API_TOKEN`, `ABSURD_EMBEDDINGS_MODEL`) the detector gets a
third tier: cosine similarity between the step description and a tool's
name+capabilities, gated by a threshold.

The tier is a fallback, never an override: schema compatibility remains the
authoritative v1 signal, and the semantic tier only lifts the *lexical*
signal for steps without declared schemas. With no embedding service
configured everything degrades to today's exact behavior.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from typing import Any

from app import config

DEFAULT_THRESHOLD = 0.5


class EmbeddingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EmbeddingTransport:
    """Minimal OpenAI-compatible embeddings client (stdlib only)."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.api_token = api_token.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_token and self.model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.available:
            raise EmbeddingError("embeddings_unavailable", "no embedding transport configured")
        body = json.dumps({"model": self.model, "input": texts})
        request = urllib.request.Request(
            self.base_url + "/embeddings",
            data=body.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise EmbeddingError("embeddings_http_error", f"embedding service returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise EmbeddingError("embeddings_unreachable", f"embedding service unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise EmbeddingError("embeddings_timeout", "embedding service timed out") from exc
        try:
            items = sorted(data["data"], key=lambda item: item["index"])
            return [list(map(float, item["embedding"])) for item in items]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise EmbeddingError("invalid_embeddings", "embedding service returned malformed data") from exc


class SemanticService:
    """Cosine-similarity tier over the embedding transport, with a cache."""

    def __init__(
        self,
        transport: EmbeddingTransport | None = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self.transport: EmbeddingTransport | None = transport
        self.threshold = threshold
        self._cache: dict[str, list[float]] = {}

    @staticmethod
    def _from_env() -> EmbeddingTransport | None:
        transport = EmbeddingTransport(
            base_url=config.EMBEDDINGS_BASE_URL,
            api_token=config.EMBEDDINGS_API_TOKEN,
            model=config.EMBEDDINGS_MODEL,
            timeout_seconds=config.EMBEDDINGS_TIMEOUT_SECONDS,
        )
        return transport if transport.available else None

    @property
    def available(self) -> bool:
        return self.transport is not None and self.transport.available

    def reset(self) -> None:
        """Re-derive the transport from configuration (test isolation)."""
        self.transport = self._from_env()
        self._cache.clear()

    def _embed(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = self.transport.embed([text])[0]
        self._cache[text] = vector
        return vector

    def similarity(self, left: str, right: str) -> float:
        if not self.available:
            return 0.0
        a, b = self._embed(left), self._embed(right)
        return SemanticService._cosine(a, b)

    def matches(self, tool: Any, description: str) -> bool:
        """Threshold-gated semantic match against name + capabilities."""
        return (
            self.available
            and self.similarity(description, f"{tool.name} {' '.join(tool.capabilities)}")
            >= self.threshold
        )

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)


semantic_service = SemanticService(
    transport=SemanticService._from_env(),
    threshold=float(config.EMBEDDING_THRESHOLD),
)