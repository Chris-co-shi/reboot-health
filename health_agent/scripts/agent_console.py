"""Interactive Agent Console for the Python Health Agent Harness.

This script is a local harness surface around AgentCore/AgentLoop. It never
persists confirmed health facts and never bypasses the Provider/Skill runtime.
Saved runs are redacted summaries intended for local review only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.models.base import ProviderConfigurationError
from agent.models.openai_compatible import OpenAICompatibleProvider
from agent.runtime.core import AgentCore


CONSOLE_SUMMARY_SCHEMA_VERSION = "health-agent.console-run-summary.v0"
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs"

DIAGNOSTIC_DEFAULTS = {
    "REBOOT_HEALTH_MODEL_DEBUG_LOG": "false",
    "REBOOT_HEALTH_MODEL_LOG_REQUEST": "none",
    "REBOOT_HEALTH_MODEL_LOG_RESPONSE": "none",
    "REBOOT_HEALTH_AGENT_DEBUG_TRACE": "false",
}


@dataclass
class ConsoleState:
    """Mutable local console state."""

    provider_name: str = "mock"
    user_text: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    goals: list[Any] = field(default_factory=list)
    constraints: list[Any] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    last_result: dict[str, Any] | None = None
    last_payload: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Build the AgentLoop payload from current console state."""
        return {
            "userText": self.user_text,
            "profile": dict(self.profile),
            "knownHealthConstraints": list(self.constraints),
            "goals": list(self.goals),
            "preferences": dict(self.preferences),
        }

    def reset(self) -> None:
        """Clear local console context and last run."""
        self.user_text = ""
        self.profile.clear()
        self.goals.clear()
        self.constraints.clear()
        self.preferences.clear()
        self.last_result = None
        self.last_payload = None


def main(argv: list[str] | None = None) -> None:
    """Run one-shot mode when --user-text is present; otherwise start REPL."""
    args = _parse_args(argv)
    _load_dotenv_file(PROJECT_ROOT / ".env")
    _apply_diagnostic_defaults()
    _configure_logging(
        _env_flag("REBOOT_HEALTH_MODEL_DEBUG_LOG")
        or _env_flag("REBOOT_HEALTH_AGENT_DEBUG_TRACE")
    )

    state = ConsoleState(
        provider_name=_normalize_provider(
            args.provider or os.environ.get("REBOOT_HEALTH_AGENT_PROVIDER") or "mock"
        )
    )
    if args.profile_file:
        _load_profile_file_into_state(Path(args.profile_file), state)
    if args.user_text is not None:
        state.user_text = args.user_text.strip()
        _run_once(state, print_trace=args.print_trace, save_run=args.save_run)
        return

    _run_repl(state)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse console arguments."""
    parser = argparse.ArgumentParser(description="Run the Health Agent console.")
    parser.add_argument("--user-text", help="Run once with this user text.")
    parser.add_argument("--profile-file", help="Load a local JSON profile before run.")
    parser.add_argument(
        "--provider",
        choices=("mock", "openai-compatible"),
        help="Provider to use. Defaults to REBOOT_HEALTH_AGENT_PROVIDER or mock.",
    )
    parser.add_argument(
        "--print-trace",
        action="store_true",
        help="Print a redacted trace in one-shot output.",
    )
    parser.add_argument(
        "--save-run",
        action="store_true",
        help="Save a redacted run summary under health_agent/runs/.",
    )
    return parser.parse_args(argv)


def _run_once(state: ConsoleState, print_trace: bool, save_run: bool) -> None:
    """Execute one AgentLoop run and print a redacted summary."""
    try:
        _run_agent(state)
    except ProviderConfigurationError as exc:
        print(
            json.dumps(
                _configuration_error_summary(state.provider_name, exc),
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)

    summary = _run_summary(state, include_trace=print_trace)
    saved_path = None
    if save_run:
        saved_path = _save_run_summary(state, None)
        summary["savedRunPath"] = str(saved_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("error"):
        raise SystemExit(1)


def _run_repl(state: ConsoleState) -> None:
    """Start an interactive console REPL."""
    print("Health Agent Console. 输入 /help 查看命令，普通文本会设置为本次 userText。")
    while True:
        try:
            raw_line = input("health-agent> ")
        except EOFError:
            print()
            return
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("/"):
            state.user_text = line
            print(f"已设置 userText（{len(state.user_text)} chars）。")
            continue
        try:
            should_continue = _handle_command(line, state)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: {_redact_text(str(exc), state)}")
            continue
        if not should_continue:
            return


def _handle_command(line: str, state: ConsoleState) -> bool:
    """Handle a slash command. Returns False when the REPL should exit."""
    if line in ("/exit", "/quit"):
        return False
    if line == "/help":
        print(_help_text())
        return True
    if line == "/profile":
        print(json.dumps(_profile_summary(state), ensure_ascii=False, indent=2))
        return True
    if line.startswith("/profile load "):
        path = line[len("/profile load "):].strip()
        _load_profile_file_into_state(Path(path), state)
        print("profile loaded")
        return True
    if line.startswith("/profile set "):
        assignment = line[len("/profile set "):].strip()
        _set_key_value(state.profile, assignment)
        print("profile updated")
        return True
    if line.startswith("/goal add "):
        text = line[len("/goal add "):].strip()
        if text:
            state.goals.append({"name": text})
        print(f"goals={len(state.goals)}")
        return True
    if line.startswith("/constraint add "):
        text = line[len("/constraint add "):].strip()
        if text:
            state.constraints.append({"name": text})
        print(f"constraints={len(state.constraints)}")
        return True
    if line.startswith("/preference set "):
        assignment = line[len("/preference set "):].strip()
        _set_key_value(state.preferences, assignment)
        print("preferences updated")
        return True
    if line == "/run":
        try:
            _run_agent(state)
        except ProviderConfigurationError as exc:
            print(
                json.dumps(
                    _configuration_error_summary(state.provider_name, exc),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return True
        print(json.dumps(_run_summary(state, include_trace=False), ensure_ascii=False, indent=2))
        return True
    if line == "/output":
        if state.last_result is None:
            print("no run output")
        else:
            print(json.dumps(_run_summary(state, include_trace=False), ensure_ascii=False, indent=2))
        return True
    if line == "/trace":
        if state.last_result is None:
            print("no run trace")
        else:
            print(json.dumps(_redacted_trace(state), ensure_ascii=False, indent=2))
        return True
    if line.startswith("/save "):
        path = line[len("/save "):].strip()
        if not path:
            print("usage: /save <path>")
            return True
        saved_path = _save_run_summary(state, Path(path))
        print(f"saved: {saved_path}")
        return True
    if line == "/reset":
        state.reset()
        print("console state reset")
        return True
    print(f"unknown command: {line}")
    return True


def _run_agent(state: ConsoleState) -> dict[str, Any]:
    """Run INITIAL_PLANNING through AgentCore/AgentLoop."""
    provider = _build_provider(state.provider_name)
    payload = state.to_payload()
    result = AgentCore.default(provider=provider).run_detailed(
        "INITIAL_PLANNING",
        payload,
    )
    state.last_payload = payload
    state.last_result = result.to_dict()
    return state.last_result


def _build_provider(provider_name: str):
    """Build the configured provider. Mock is represented by None."""
    if provider_name == "openai-compatible":
        return OpenAICompatibleProvider(debug_log=_env_flag("REBOOT_HEALTH_MODEL_DEBUG_LOG"))
    return None


def _load_profile_file_into_state(path: Path, state: ConsoleState) -> None:
    """Load a local JSON profile into console state."""
    profile_path = path.expanduser()
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("profile file must contain a JSON object")

    if isinstance(data.get("profile"), Mapping):
        state.profile.update(dict(data["profile"]))
    else:
        profile_keys = {
            key: value
            for key, value in data.items()
            if key
            not in {
                "userText",
                "goals",
                "knownHealthConstraints",
                "constraints",
                "preferences",
            }
        }
        state.profile.update(profile_keys)

    if str(data.get("userText") or "").strip():
        state.user_text = str(data["userText"]).strip()
    if isinstance(data.get("goals"), list):
        state.goals = list(data["goals"])
    constraints = data.get("knownHealthConstraints", data.get("constraints"))
    if isinstance(constraints, list):
        state.constraints = list(constraints)
    if isinstance(data.get("preferences"), Mapping):
        state.preferences.update(dict(data["preferences"]))


def _set_key_value(target: dict[str, Any], assignment: str) -> None:
    """Set a simple or dotted key from key=value text."""
    if "=" not in assignment:
        raise ValueError("assignment must be key=value")
    key, raw_value = assignment.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError("assignment key is required")
    value = _parse_value(raw_value.strip())
    current = target
    parts = [part for part in key.split(".") if part]
    if not parts:
        raise ValueError("assignment key is required")
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _parse_value(raw_value: str) -> Any:
    """Parse a command value as JSON when possible; otherwise keep string."""
    if not raw_value:
        return ""
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value


def _save_run_summary(state: ConsoleState, path: Path | None) -> Path:
    """Save only a redacted run summary."""
    if state.last_result is None:
        raise ValueError("no run to save")
    if path is None:
        run_id = str(state.last_result.get("runId") or "run")
        path = DEFAULT_RUNS_DIR / f"{run_id}.summary.json"
    target_path = path.expanduser()
    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(_run_summary(state, include_trace=False), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_path


def _run_summary(state: ConsoleState, include_trace: bool) -> dict[str, Any]:
    """Build a redacted summary of the last run."""
    if state.last_result is None:
        return {
            "schemaVersion": CONSOLE_SUMMARY_SCHEMA_VERSION,
            "status": "empty",
            "provider": state.provider_name,
            "error": {"code": "no_run", "message": "No run has been executed."},
        }

    result = state.last_result
    output = result.get("output") or {}
    trace = result.get("trace") or {}
    warnings = result.get("warnings") or []
    summary = {
        "schemaVersion": CONSOLE_SUMMARY_SCHEMA_VERSION,
        "savedAt": datetime.now(timezone.utc).isoformat(),
        "provider": state.provider_name,
        "runId": result.get("runId"),
        "sessionId": result.get("sessionId"),
        "status": result.get("status"),
        "selectedSkill": result.get("selectedSkill"),
        "finalOutcome": result.get("finalOutcome"),
        "output": {
            "schemaVersion": output.get("schemaVersion"),
            "requiresUserConfirmation": output.get("requiresUserConfirmation"),
            "hasProgramDraft": isinstance(output.get("programDraft"), dict),
            "hasWeeklyPlanDraft": isinstance(output.get("weeklyPlanDraft"), dict),
            "hasTodayActionDraft": isinstance(output.get("todayActionDraft"), dict),
            "todayActionDraft": _redacted_preview(output.get("todayActionDraft"), state),
            "safetyNotes": _redacted_preview(output.get("safetyNotes"), state),
            "questions": _redacted_preview(output.get("questions"), state),
        },
        "memoryCandidatesPreview": _memory_candidates_preview(
            result.get("memoryCandidates") or [],
            state,
        ),
        "warningCount": len(warnings),
        "warnings": _redacted_preview(warnings, state),
        "traceSummary": {
            "provider": trace.get("provider"),
            "selectedSkill": trace.get("selectedSkill"),
            "finalOutcome": trace.get("finalOutcome"),
            "stepNames": [
                step.get("name")
                for step in trace.get("steps", [])
                if isinstance(step, Mapping)
            ],
            "warningCount": len(trace.get("warnings") or []),
        },
        "error": _redacted_error(result.get("error"), state),
    }
    if include_trace:
        summary["trace"] = _redacted_trace(state)
    return summary


def _redacted_trace(state: ConsoleState) -> object:
    """Return a redacted trace for stdout diagnostics."""
    trace = (state.last_result or {}).get("trace")
    return _redacted_preview(trace, state, max_depth=6, max_list_items=30)


def _profile_summary(state: ConsoleState) -> dict[str, Any]:
    """Return local profile state without dumping complete user text."""
    return {
        "provider": state.provider_name,
        "hasUserText": bool(state.user_text),
        "userTextChars": len(state.user_text),
        "profile": _redacted_preview(state.profile, state),
        "goals": _redacted_preview(state.goals, state),
        "knownHealthConstraints": _redacted_preview(state.constraints, state),
        "preferences": _redacted_preview(state.preferences, state),
        "hasLastRun": state.last_result is not None,
    }


def _memory_candidates_preview(candidates: object, state: ConsoleState) -> dict[str, Any]:
    """Summarize memory candidates without saving full candidate content."""
    if not isinstance(candidates, list):
        return {"count": 0, "items": []}
    items = []
    for candidate in candidates[:5]:
        if not isinstance(candidate, Mapping):
            continue
        item = {
            "kind": candidate.get("kind"),
            "confidence": candidate.get("confidence"),
            "requiresUserConfirmation": candidate.get("requiresUserConfirmation"),
        }
        if candidate.get("content") is not None:
            item["contentPreview"] = _redacted_preview(
                candidate.get("content"),
                state,
                max_depth=1,
                max_string_length=80,
            )
        items.append(item)
    return {
        "count": len(candidates),
        "items": items,
        "truncatedItemCount": max(0, len(candidates) - len(items)),
    }


def _redacted_preview(
    value: object,
    state: ConsoleState,
    max_depth: int = 5,
    max_list_items: int = 8,
    max_dict_items: int = 24,
    max_string_length: int = 180,
) -> object:
    """Recursively redact and truncate local output for console display/save."""
    if max_depth < 0:
        return _type_summary(value)
    if isinstance(value, Mapping):
        preview: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_dict_items:
                preview["_truncatedKeys"] = len(value) - max_dict_items
                break
            key_text = str(key)
            if _is_sensitive_key(key_text):
                preview[key_text] = "<redacted>"
            else:
                preview[key_text] = _redacted_preview(
                    item,
                    state,
                    max_depth=max_depth - 1,
                    max_list_items=max_list_items,
                    max_dict_items=max_dict_items,
                    max_string_length=max_string_length,
                )
        return preview
    if isinstance(value, list | tuple):
        items = [
            _redacted_preview(
                item,
                state,
                max_depth=max_depth - 1,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
                max_string_length=max_string_length,
            )
            for item in list(value)[:max_list_items]
        ]
        if len(value) > max_list_items:
            items.append({"_truncatedItems": len(value) - max_list_items})
        return items
    if isinstance(value, str):
        return _truncate_text(_redact_text(value, state), max_string_length)
    return value


def _type_summary(value: object) -> object:
    """Return type-only summary when max depth is exceeded."""
    if isinstance(value, Mapping):
        return {"_type": "object", "keyCount": len(value)}
    if isinstance(value, list | tuple):
        return {"_type": "list", "itemCount": len(value)}
    if isinstance(value, str):
        return {"_type": "string", "chars": len(value)}
    return value


def _redacted_error(error: object, state: ConsoleState) -> object:
    """Redact error content."""
    if not isinstance(error, Mapping):
        return error
    return {
        str(key): _redacted_preview(value, state)
        for key, value in error.items()
        if not _is_sensitive_key(str(key))
    }


def _configuration_error_summary(provider_name: str, exc: Exception) -> dict[str, Any]:
    """Return a structured provider configuration error."""
    state = ConsoleState(provider_name=provider_name)
    return {
        "schemaVersion": CONSOLE_SUMMARY_SCHEMA_VERSION,
        "provider": provider_name,
        "status": "failed",
        "finalOutcome": "failed",
        "error": {
            "code": "missing_config",
            "message": _redact_text(str(exc), state),
        },
    }


def _redact_text(value: str, state: ConsoleState) -> str:
    """Redact tokens, configured keys, and the full local user text."""
    text = re.sub(r"Bearer\s+\S+", "Bearer <redacted>", value)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-<redacted>", text)
    for key in (
        os.environ.get("REBOOT_HEALTH_MODEL_API_KEY"),
        os.environ.get("AGENT_OPENAI_API_KEY"),
        state.user_text,
    ):
        if key:
            text = text.replace(str(key), "<redacted>")
    return text


def _truncate_text(value: str, max_length: int) -> str:
    """Truncate long strings."""
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}...<truncated>"


def _is_sensitive_key(key: str) -> bool:
    """Detect keys that should never be printed or saved."""
    normalized = key.lower().replace("-", "_")
    return (
        normalized
        in {
            "api_key",
            "apikey",
            "authorization",
            "auth_token",
            "access_token",
            "refresh_token",
            "token",
            "secret",
            "client_secret",
            "password",
        }
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
    )


def _load_dotenv_file(path: Path) -> tuple[str, ...]:
    """Load missing environment values from a minimal .env file."""
    if not path.exists():
        return ()
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)


def _parse_dotenv_line(raw_line: str) -> tuple[str, str] | None:
    """Parse a minimal dotenv line."""
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export "):].strip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    else:
        value = value.split(" #", 1)[0].rstrip()
    return key, value


def _apply_diagnostic_defaults() -> tuple[str, ...]:
    """Apply safe diagnostic defaults when not configured."""
    applied: list[str] = []
    for key, value in DIAGNOSTIC_DEFAULTS.items():
        if str(os.environ.get(key) or "").strip():
            continue
        os.environ[key] = value
        applied.append(key)
    return tuple(applied)


def _configure_logging(enabled: bool) -> None:
    """Enable local diagnostic logs."""
    if not enabled:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _env_flag(name: str) -> bool:
    """Read a boolean environment flag."""
    return str(os.environ.get(name) or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "debug",
    )


def _normalize_provider(value: str) -> str:
    """Normalize provider name."""
    normalized = value.strip().lower().replace("_", "-")
    if normalized in ("openai", "openai-compatible"):
        return "openai-compatible"
    return "mock"


def _help_text() -> str:
    """Return REPL help."""
    return """Commands:
  /help
  /profile
  /profile load <path>
  /profile set <key>=<value>
  /goal add <text>
  /constraint add <text>
  /preference set <key>=<value>
  /run
  /output
  /trace
  /save <path>
  /reset
  /exit

Non-command input sets the current userText for the next /run.
"""


if __name__ == "__main__":
    main()
