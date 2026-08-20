"""Tool execution sandbox (Phase 13a).

Runs a registered tool's `source_code` in a fresh, isolated Python
subprocess and turns the outcome into an `ExecutionRecord` with honest
statuses and events:

- `SECURITY_REJECTED` — the AST policy pass blocked the source (imports,
  eval/exec, file/network access, dunder attribute traversal).
- `TIMEOUT` — the subprocess exceeded its execution budget and was killed.
- `FAILED` — input/output validation errors or a runtime error in the tool.
- `COMPLETED` — the tool returned a JSON object matching its output schema.

The AST policy is defense-in-depth: the subprocess runs with `python -I`
(ignored environment, no user site-packages), a throwaway working directory,
no inherited stdin beyond the JSON payload, and a hard wall-clock timeout.
Tools are single public functions taking `inputs: dict` and returning a
JSON-serializable dict; nothing else is supported and everything else fails
loudly. Execution requires an already REGISTERED tool (enforced by the API).
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.agent.detector import CapabilityDetector
from app.core.tools.model import ToolStatus
from app.events import EventType, bus
from app.models import ExecutionRecord, ToolRecord
from app.services.generator import sanitize_name

EXECUTION_TIMEOUT_DEFAULT = 10.0
MAX_TIMEOUT_SECONDS = 30.0
MAX_OUTPUT_BYTES = 1_000_000
MAX_ERROR_BYTES = 2_000

# Calls that may escape the sandbox or reach the host.
_FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "input",
    "breakpoint",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "memoryview",
    "exit",
    "quit",
    "help",
}

# Attribute access that can leak frame/class internals.
_FORBIDDEN_ATTRS = {
    "func_globals",
    "gi_frame",
    "cr_frame",
    "f_back",
    "tb_frame",
    "tb_next",
    "f_locals",
    "gi_code",
    "cr_code",
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__class__",
    "__bases__",
    "__mro__",
    "__code__",
    "__dict__",
    "__module__",
    "__loader__",
    "__spec__",
}


@dataclass
class PolicyDecision:
    allowed: bool
    violations: list[str]


class _PolicyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.violations.append(f"imports are not allowed ('{node.names[0].name}')")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.violations.append(f"imports are not allowed ('from {node.module} import ...')")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
            self.violations.append(f"use of '{node.func.id}()' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        attr = node.attr
        if attr in _FORBIDDEN_ATTRS or attr.startswith("_"):
            self.violations.append(f"attribute access to '{attr}' is not allowed")
        self.generic_visit(node)


def check_policy(source_code: str) -> PolicyDecision:
    """AST policy gate: no imports, no eval/exec, no duck-typed escapes."""
    visitor = _PolicyVisitor()
    visitor.visit(ast.parse(source_code))
    return PolicyDecision(allowed=not visitor.violations, violations=visitor.violations)


def _extract_function_name(source_code: str, tool_name: str) -> str | None:
    """Name of the top-level public function to invoke, or None."""
    tree = ast.parse(source_code)
    defs = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
    ]
    if not defs:
        return None
    expected = sanitize_name(tool_name)
    return next((name for name in defs if name == expected), defs[0])


def _validate_inputs(input_schema: dict[str, Any], inputs: dict[str, Any]) -> list[str]:
    return [
        f"missing required input '{key}'"
        for key in input_schema
        if key not in inputs
    ]


def _validate_output(output_schema: dict[str, Any], value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["output must be a JSON object"]
    errors: list[str] = []
    for key, declared in output_schema.items():
        if key not in value:
            errors.append(f"missing output key '{key}'")
            continue
        actual = type(value[key]).__name__
        if not CapabilityDetector._type_compatible(declared, actual):
            errors.append(f"output '{key}': expected {declared}, got {actual}")
    return errors


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return payload


class ToolSandbox:
    def execute(
        self,
        session: Session,
        tool: ToolRecord,
        inputs: dict[str, Any],
        *,
        task_id: str = "",
        timeout_seconds: float = EXECUTION_TIMEOUT_DEFAULT,
    ) -> ExecutionRecord:
        """Run the tool once and persist an honest ExecutionRecord."""
        record = ExecutionRecord(
            id=uuid4().hex,
            task_id=task_id,
            tool_id=tool.id,
            tool_version=tool.version,
            status="RUNNING",
            input=dict(inputs),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        bus.publish(
            EventType.TOOL_EXECUTION_STARTED,
            {"tool_id": tool.id, "tool_version": tool.version, "task_id": task_id},
        )
        bus.publish(EventType.SANDBOX_STARTED, {"tool_id": tool.id, "task_id": task_id})

        started = time.perf_counter()
        if tool.status != ToolStatus.REGISTERED.value:
            status, output, error, extra = "FAILED", None, _error(
                "not_registered", f"tool {tool.id} is not REGISTERED"
            ), {}
        else:
            status, output, error, extra = self._run(tool, inputs, timeout_seconds)
        duration_ms = int((time.perf_counter() - started) * 1000)

        record.status = status
        record.output = output
        record.error = error
        record.metrics = {
            "duration_ms": duration_ms,
            "exit_code": extra.get("exit_code"),
            "policy_allowed": extra.get("policy_allowed", True),
            "timeout_seconds": timeout_seconds,
        }
        record.finished_at = datetime.now(timezone.utc)
        session.add(record)
        session.commit()
        session.refresh(record)

        if status == "SECURITY_REJECTED":
            bus.publish(
                EventType.SECURITY_VIOLATION,
                {"tool_id": tool.id, "task_id": task_id, "violations": extra.get("violations", [])},
            )
        elif status == "TIMEOUT":
            bus.publish(EventType.SANDBOX_TIMEOUT, {"tool_id": tool.id, "task_id": task_id})
        elif status == "COMPLETED":
            bus.publish(
                EventType.EXECUTION_COMPLETED,
                {"tool_id": tool.id, "task_id": task_id, "output": output},
            )
        else:
            bus.publish(
                EventType.EXECUTION_FAILED,
                {"tool_id": tool.id, "task_id": task_id, "code": error["code"] if error else "execution_failed"},
            )
        bus.publish(
            EventType.TOOL_EXECUTION_FINISHED,
            {
                "tool_id": tool.id,
                "tool_version": tool.version,
                "task_id": task_id,
                "status": status,
                "code": error.get("code") if error else None,
            },
        )
        return record

    def run_tests(
        self,
        tool: ToolRecord,
        *,
        timeout_seconds: float = EXECUTION_TIMEOUT_DEFAULT,
    ) -> dict[str, Any]:
        """Behavioral gate (Phase 13c): run the tool's stored tests in the sandbox.

        Every test fragment is executed in one isolated subprocess against the
        tool's module globals (so tests may reference the function by name or
        via `fn`). A policy violation in source or tests, a syntax error, a
        timeout, or a failing assertion all report per-test detail openly.
        Test runs are annex observability — they do not write ExecutionRecords.
        """
        bucket: dict[str, Any] = {"available": True}
        started = time.perf_counter()

        def failed_with(code: str, message: str) -> dict[str, Any]:
            return self._behavioral_result(bucket, started, code, message)

        tests = list(tool.tests or [])
        if not tests:
            return failed_with("no_tests", "tool declares no tests; nothing to run")

        try:
            source_decision = check_policy(tool.source_code)
        except SyntaxError as exc:
            return failed_with("invalid_source", f"syntax error: {exc.msg}")
        if not source_decision.allowed:
            return self._behavioral_result(
                bucket,
                started,
                "security_violation",
                "; ".join(source_decision.violations[:5]),
                source_allowed=False,
            )

        test_decision = check_policy("\n".join(tests))
        if not test_decision.allowed:
            return self._behavioral_result(
                bucket,
                started,
                "security_violation",
                "; ".join(test_decision.violations[:5]),
                test_allowed=False,
            )

        func_name = _extract_function_name(tool.source_code, tool.name)
        if func_name is None:
            return failed_with("invalid_source", "no public function found in source code")

        workdir = Path(tempfile.mkdtemp(prefix="absurd-sandbox-"))
        try:
            (workdir / "tool_module.py").write_text(tool.source_code, encoding="utf-8")
            script = (
                "import json, sys\n"
                f"sys.path.insert(0, {str(workdir)!r})\n"
                "import tool_module as _tool\n"
                "G = vars(_tool)\n"
                f"fn = G[{func_name!r}]\n"
                f"TESTS = {json.dumps(tests)}\n"
                "out = []\n"
                "for code in TESTS:\n"
                "    try:\n"
                "        exec(code, G)\n"
                "        out.append({'passed': True, 'error': None})\n"
                "    except Exception as exc:\n"
                "        out.append({'passed': False, 'error': f'{type(exc).__name__}: {exc}'})\n"
                "print(json.dumps(out))\n"
            )
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-c", script],
                    capture_output=True,
                    cwd=str(workdir),
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return failed_with("timeout", f"test run exceeded {timeout_seconds:g}s and was killed")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        if len(stdout) > MAX_OUTPUT_BYTES:
            return failed_with("output_too_large", f"test output exceeded {MAX_OUTPUT_BYTES} bytes")
        try:
            outcomes = json.loads(stdout)
        except json.JSONDecodeError:
            detail = (stderr or stdout).strip().splitlines()
            message = detail[-1] if detail else "test runner produced no JSON report"
            return failed_with("invalid_report", message[:MAX_ERROR_BYTES])
        if not isinstance(outcomes, list) or len(outcomes) != len(tests):
            return failed_with("invalid_report", "test runner returned a malformed report")

        details = [
            {"test": (outcome.get("test") or tests[index])[:200],
             "passed": bool(outcome.get("passed")),
             "error": outcome.get("error")}
            for index, outcome in enumerate(outcomes)
        ]
        passed = all(item["passed"] for item in details)
        return {
            **bucket,
            "passed": passed,
            "tests_total": len(tests),
            "tests_passed": sum(1 for item in details if item["passed"]),
            "details": details,
            "policy": {
                "source_allowed": True,
                "test_allowed": True,
                "violations": [],
            },
            "error": None,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    @staticmethod
    def _behavioral_result(
        bucket: dict[str, Any],
        started: float,
        code: str,
        message: str,
        *,
        source_allowed: bool = True,
        test_allowed: bool = True,
    ) -> dict[str, Any]:
        """Shared shape for every non-run failure of the behavioral gate."""
        return {
            **bucket,
            "passed": False,
            "tests_passed": 0,
            "details": [],
            "policy": {
                "source_allowed": source_allowed,
                "test_allowed": test_allowed,
                "violations": [],
            },
            "error": code,
            "error_message": message,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    def _run(
        self,
        tool: ToolRecord,
        inputs: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
        try:
            decision = check_policy(tool.source_code)
        except SyntaxError as exc:
            return "FAILED", None, _error("invalid_source", f"syntax error: {exc.msg}"), {"policy_allowed": False}
        if not decision.allowed:
            return "SECURITY_REJECTED", None, _error(
                "security_violation",
                "; ".join(decision.violations[:5]),
                violations=decision.violations,
            ), {"policy_allowed": False, "violations": decision.violations}

        func_name = _extract_function_name(tool.source_code, tool.name)
        if func_name is None:
            return "FAILED", None, _error(
                "invalid_source", "no public function found; tools must define one top-level function"
            ), {"policy_allowed": True}

        missing = _validate_inputs(tool.input_schema or {}, inputs)
        if missing:
            return "FAILED", None, _error(
                "input_validation", "; ".join(missing)
            ), {"policy_allowed": True}

        workdir = Path(tempfile.mkdtemp(prefix="absurd-sandbox-"))
        try:
            (workdir / "tool_module.py").write_text(tool.source_code, encoding="utf-8")
            script = (
                "import json, sys\n"
                f"sys.path.insert(0, {str(workdir)!r})\n"
                "import tool_module as _tool\n"
                f"fn = _tool.{func_name}\n"
                "raw = sys.stdin.read()\n"
                "inputs = json.loads(raw) if raw.strip() else {}\n"
                "result = fn(inputs)\n"
                "print(json.dumps(result))\n"
            )
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-c", script],
                    input=json.dumps(inputs).encode("utf-8"),
                    capture_output=True,
                    cwd=str(workdir),
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return "TIMEOUT", None, _error(
                    "timeout", f"execution exceeded {timeout_seconds:g}s and was killed"
                ), {"policy_allowed": True, "exit_code": None}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            detail = (stderr or stdout).strip().splitlines()
            message = detail[-1] if detail else f"process exited with code {proc.returncode}"
            return "FAILED", None, _error(
                "runtime_error", message[:MAX_ERROR_BYTES]
            ), {"policy_allowed": True, "exit_code": proc.returncode}
        if len(stdout) > MAX_OUTPUT_BYTES:
            return "FAILED", None, _error(
                "output_too_large", f"output exceeded {MAX_OUTPUT_BYTES} bytes"
            ), {"policy_allowed": True, "exit_code": proc.returncode}

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            return "FAILED", None, _error(
                "invalid_output", "tool did not print a single JSON object"
            ), {"policy_allowed": True, "exit_code": proc.returncode}

        output_errors = _validate_output(tool.output_schema or {}, output)
        if output_errors:
            return "FAILED", None, _error(
                "output_validation", "; ".join(output_errors)
            ), {"policy_allowed": True, "exit_code": proc.returncode}
        return "COMPLETED", output, None, {"policy_allowed": True, "exit_code": proc.returncode}


sandbox = ToolSandbox()