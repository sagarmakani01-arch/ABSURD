"""Optional LLM transport (Phase 13d).

An OpenAI-compatible chat-completions client used for two jobs, both gated on
runtime configuration (`ABSURD_LLM_BASE_URL`, `ABSURD_LLM_API_TOKEN`,
`ABSURD_LLM_MODEL`):

- tool generation — the model writes the body of a candidate tool from a
  `GapSpec` (schemas stay bound to the gap contract; the model provides the
  behavior);
- tool revision — the model rewrites a failing tool's source from real
  execution feedback.

With no configuration the transport is unavailable and ABSURD degrades
honestly: generation falls back to the deterministic template strategy and
revisions fail with the documented `revision_generation_unavailable` 409.
Model output is validated before it can enter the registry (source compiles,
passes the sandbox AST policy, keeps a public `inputs: dict -> dict`
function; tests are policy-checked too). The transport never fabricates
`available = True`; tests inject their own in-process transport subclass.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from app import config


class LLMError(Exception):
    """Structured model-service failure; callers fail closed, never guess."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_SYSTEM_GENERATE = (
    "You are the tool generator for ABSURD, a self-extending agent runtime. "
    "Write one pure Python function taking a single argument named `inputs` "
    "(a dict) and returning a dict. The function must implement the declared "
    "behavior with the standard library only. NO imports are allowed in the "
    "generated source. Reply with strict JSON only, with keys: source_code "
    "(str), tests (list of str, each an assert fragment that runs against the "
    "module), description (str)."
)

_SYSTEM_REVISE = (
    "You are the tool repairer for ABSURD. Rewrite the given tool so it "
    "satisfies its declared input/output schema and passes its tests, using "
    "the reported execution feedback. Keep the same single public function "
    "name and the `def <name>(inputs: dict) -> dict` signature. NO imports "
    "allowed. Reply with strict JSON only, with keys: source_code (str), "
    "tests (list of str), description (str)."
)


class LLMTransport:
    """Minimal OpenAI-compatible chat-completions client (stdlib only)."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.api_token = api_token.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_token and self.model)

    def generate_tool(self, gap_spec: Any) -> dict[str, Any]:
        """Ask the model for `{source_code, tests, description}` for a gap."""
        if not self.available:
            raise LLMError("llm_unavailable", "no LLM transport configured")
        messages = [
            {"role": "system", "content": _SYSTEM_GENERATE},
            {"role": "user", "content": json.dumps({"gap_spec": gap_spec.model_dump()})},
        ]
        return self._bundle(self._chat_json(messages))

    def revise_tool(self, tool: Any, feedback: list[str]) -> dict[str, Any]:
        """Ask the model to repair a failing tool from real feedback."""
        if not self.available:
            raise LLMError("llm_unavailable", "no LLM transport configured")
        user_payload = {
            "tool": {
                "name": tool.name,
                "description": tool.description,
                "source_code": tool.source_code,
                "tests": tool.tests,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
            },
            "feedback": feedback,
        }
        messages = [
            {"role": "system", "content": _SYSTEM_REVISE},
            {"role": "user", "content": json.dumps(user_payload)},
        ]
        return self._bundle(self._chat_json(messages))

    @classmethod
    def _validate_bundle(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Contract check: source, tests, description must be usable."""
        from app.services.sandbox import _extract_function_name, check_policy

        source = payload.get("source_code")
        tests = payload.get("tests")
        description = payload.get("description")

        if not isinstance(source, str) or not source.strip():
            raise LLMError("invalid_llm_output", "model returned no source_code")
        try:
            decision = check_policy(source)
        except SyntaxError as exc:
            raise LLMError(
                "invalid_llm_output", f"model source does not parse: {exc.msg}"
            ) from exc
        if not decision.allowed:
            raise LLMError(
                "invalid_llm_output",
                "model source violates the sandbox policy: " + "; ".join(decision.violations[:3]),
            )
        if _extract_function_name(source, "") is None:
            raise LLMError(
                "invalid_llm_output",
                "model source has no public function taking `inputs`",
            )
        if not isinstance(tests, list) or not tests or not all(isinstance(t, str) for t in tests):
            raise LLMError("invalid_llm_output", "model returned no usable tests")
        if not check_policy("\n".join(tests)).allowed:
            raise LLMError("invalid_llm_output", "model tests violate the sandbox policy")
        return {
            "source_code": source,
            "tests": tests,
            "description": description if isinstance(description, str) else "",
        }

    def _bundle(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            content = str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("invalid_llm_output", "model response had no message content") from exc
        return self._validate_bundle(self._extract_json(content))

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            start, end = stripped.find("{"), stripped.rfind("}")
            if start == -1 or end <= start:
                raise LLMError("invalid_llm_output", "model response was not JSON") from None
            try:
                data = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError as exc:
                raise LLMError("invalid_llm_output", "model response was not JSON") from exc
        if not isinstance(data, dict):
            raise LLMError("invalid_llm_output", "model response was not a JSON object")
        return data

    def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        endpoint = self.base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0.2})
        request = urllib.request.Request(
            endpoint,
            data=body.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMError("llm_http_error", f"model service returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise LLMError("llm_unreachable", f"model service unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError("llm_timeout", "model service timed out") from exc


class LLMService:
    """Holds the configured transport; degrades to unavailable when absent."""

    def __init__(self) -> None:
        self.transport: LLMTransport | None = self._from_env()

    @staticmethod
    def _from_env() -> LLMTransport | None:
        transport = LLMTransport(
            base_url=config.LLM_BASE_URL,
            api_token=config.LLM_API_TOKEN,
            model=config.LLM_MODEL,
            timeout_seconds=config.LLM_TIMEOUT_SECONDS,
        )
        return transport if transport.available else None

    @property
    def available(self) -> bool:
        return self.transport is not None and self.transport.available

    @property
    def model(self) -> str:
        return self.transport.model if self.transport else ""

    def reset(self) -> None:
        """Re-derive the transport from configuration (test isolation)."""
        self.transport = self._from_env()

    def generate_tool(self, gap_spec: Any) -> dict[str, Any]:
        if not self.available:
            raise LLMError("llm_unavailable", "no LLM transport configured")
        return self.transport.generate_tool(gap_spec)

    def revise_tool(self, tool: Any, feedback: list[str]) -> dict[str, Any]:
        if not self.available:
            raise LLMError("llm_unavailable", "no LLM transport configured")
        return self.transport.revise_tool(tool, feedback)


llm_service = LLMService()