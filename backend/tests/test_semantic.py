"""Phase 13e tests: the semantic matching tier via an in-process transport.

The fake embedding transport derives deterministic vectors from word
tokens with a synonym map ("send" ~ "dispatch", "summary" ~ "report"), so
the tier catches wording drift the lexical matcher misses. The service
re-derives its transport from configuration between tests (`reset()`), so
without the injected fake the detector behaves exactly as before.
"""

from __future__ import annotations

import math
import re

import pytest
from fastapi.testclient import TestClient

from app.core.agent.detector import CapabilityDetector
from app.main import app
from app.services.semantic import EmbeddingError, EmbeddingTransport, SemanticService, semantic_service

client = TestClient(app)

# Directional normalization: natural-language words and their tool-model
# counterparts collapse into one canonical token per cluster, so cosine
# similarity behaves like the real embeddings it stands in for.
CLUSTERS = {
    "send": "dispatch",
    "dispatch": "dispatch",
    "dispatcher": "dispatch",
    "out": "report",
    "weekly": "report",
    "summary": "report",
    "report": "report",
}
DIM = 64
_TOKEN_HASH = [0x9E3779B9, 0x85EBCA6B, 0xC2B2AE35, 0x27D4EB2F]


class FakeEmbeddingTransport(EmbeddingTransport):
    """Deterministic bag-of-tokens vectors with a synonym map."""

    def __init__(self) -> None:
        super().__init__(base_url="fake://embeddings", api_token="fake", model="fake-model")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [self._vector(text) for text in texts]
        return vectors

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * DIM
        for word in re.split(r"[\W_]+", text.lower()):
            if not word:
                continue
            token = CLUSTERS.get(word, word)
            vector[sum(ord(char) for char in token) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


@pytest.fixture()
def fake_embeddings():
    semantic_service.transport = FakeEmbeddingTransport()
    yield
    semantic_service.reset()


TOOL = {
    "name": "email_dispatcher",
    "description": "Sends the dispatched report.",
    "source_code": "def email_dispatcher(inputs: dict) -> dict:\n    return {'dispatched': True}\n",
    "capabilities": ["dispatch_report"],
    "tests": ["fn = email_dispatcher", "result = fn({})", "assert isinstance(result, dict)"],
    "input_schema": {"recipient": "str"},
    "output_schema": {"dispatched": "bool"},
}


def _register_and_activate() -> dict[str, object]:
    tool = client.post("/api/v1/tools", json=TOOL).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    return tool


def test_detector_lexical_miss_without_tier() -> None:
    tool = client.post("/api/v1/tools", json=TOOL).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    resp = client.post(
        "/api/v1/tasks",
        json={"goal": "send out the weekly summary report", "context": {}},
    )
    assert resp.json()["status"] == "FAILED"
    assert resp.json()["error"]["kind"] == "NO_CAPABILITY"


def test_semantic_tier_covers_wording_drift(fake_embeddings) -> None:
    _register_and_activate()

    task = client.post(
        "/api/v1/tasks",
        json={
            "goal": "send out the weekly summary report",
            "context": {"inputs": [{"recipient": "ops@example.com"}]},
        },
    ).json()
    assert task["status"] == "COMPLETED"
    assert task["result"]["kind"] == "EXECUTED"
    assert task["result"]["outputs"][0]["output"] == {"dispatched": True}

    metrics = client.get("/api/v1/evolution/metrics").json()
    assert metrics["embedding_available"] is True


def test_semantic_tier_never_overrides_schema_mismatch(fake_embeddings) -> None:
    """Schema compatibility stays authoritative: a semantic hit with a schema
    step that does not type-match can only be partial, not full coverage."""
    expected_io = [{"inputs": {"path": "str"}, "outputs": {"summary": "str"}}]
    tool = client.post(
        "/api/v1/tools",
        json={
            **TOOL,
            "name": "parrot_dispatcher",
            "source_code": "def parrot_dispatcher(inputs: dict) -> dict:\n    return {'summary': 'x'}\n",
            "input_schema": {"path": "str"},
            "output_schema": {"rows": "list"},
        },
    ).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    resp = client.post(
        "/api/v1/tasks",
        json={"goal": "send out the weekly summary report", "context": {"expected_io": expected_io}},
    )
    assert resp.json()["status"] == "FAILED"
    assert resp.json()["error"]["kind"] == "PARTIAL_CAPABILITY"


def test_unavailable_without_transport() -> None:
    assert semantic_service.available is False
    assert client.get("/api/v1/evolution/metrics").json()["embedding_available"] is False


def test_cosine_and_threshold_units() -> None:
    transport = FakeEmbeddingTransport()
    service = SemanticService(transport=transport, threshold=0.5)
    assert service.available is True
    assert service.similarity("send out the weekly summary report", "dispatch_report email_dispatcher") >= 0.5
    assert service.similarity("render a chart", "dispatch_report email_dispatcher") < 0.5

    # A transport actually configured for HTTP but pointing nowhere fails
    # closed with a structured error.
    broken = EmbeddingTransport(base_url="http://127.0.0.1:1", api_token="x", model="m")
    try:
        broken.embed(["hi"])
    except EmbeddingError as exc:
        assert exc.code in {"embeddings_unreachable", "embeddings_http_error", "embeddings_timeout"}
    else:
        pytest.fail("expected EmbeddingError")