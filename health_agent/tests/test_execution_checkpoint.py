import unittest
from datetime import datetime, timedelta, timezone

from agent.runtime.execution_checkpoint import (
    RunExecutionCheckpoint,
    RunExecutionCheckpointPhase,
)


class RunExecutionCheckpointTest(unittest.TestCase):
    def test_drive_ready_checkpoint_normalizes_values(self) -> None:
        checkpoint = RunExecutionCheckpoint(
            checkpoint_phase="drive_ready",
            originating_run_id=" run-1 ",
            run_fence_generation=1,
            assistant_message_index=None,
            next_tool_call_index=0,
            current_tool_call_id=None,
            current_tool_name=None,
            model_turns_used=1,
            tool_calls_used=2,
            remaining_runtime_seconds=12,
            started_at=_fixed_time(),
            deadline_at=_fixed_time() + timedelta(seconds=60),
            updated_at=_fixed_time(),
        )

        self.assertEqual(checkpoint.checkpoint_phase, RunExecutionCheckpointPhase.DRIVE_READY)
        self.assertEqual(checkpoint.originating_run_id, "run-1")
        self.assertEqual(checkpoint.remaining_runtime_seconds, 12.0)
        self.assertEqual(checkpoint.started_at.tzinfo, timezone.utc)

    def test_tool_in_flight_requires_current_tool_snapshot(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["checkpoint_phase"] = RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT

        with self.assertRaises(ValueError):
            RunExecutionCheckpoint(**kwargs)

        checkpoint = RunExecutionCheckpoint(
            **{
                **kwargs,
                "current_tool_call_id": "call-1",
                "current_tool_name": "convert_weight_unit",
            }
        )

        self.assertEqual(
            checkpoint.checkpoint_phase,
            RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT,
        )
        self.assertEqual(checkpoint.current_tool_call_id, "call-1")

    def test_non_tool_phase_rejects_current_tool(self) -> None:
        with self.assertRaises(ValueError):
            RunExecutionCheckpoint(
                **{
                    **_valid_kwargs(),
                    "current_tool_call_id": "call-1",
                    "current_tool_name": "convert_weight_unit",
                }
            )

    def test_invalid_numbers_and_time_are_rejected(self) -> None:
        for field_name in (
            "run_fence_generation",
            "next_tool_call_index",
            "model_turns_used",
            "tool_calls_used",
        ):
            with self.subTest(field_name=field_name):
                kwargs = _valid_kwargs()
                kwargs[field_name] = -1
                with self.assertRaises(ValueError):
                    RunExecutionCheckpoint(**kwargs)

        kwargs = _valid_kwargs()
        kwargs["remaining_runtime_seconds"] = -0.1
        with self.assertRaises(ValueError):
            RunExecutionCheckpoint(**kwargs)

        kwargs = _valid_kwargs()
        kwargs["updated_at"] = datetime(2026, 1, 2, 3, 4, 5)
        with self.assertRaises(ValueError):
            RunExecutionCheckpoint(**kwargs)


def _valid_kwargs() -> dict:
    return {
        "checkpoint_phase": RunExecutionCheckpointPhase.DRIVE_READY,
        "originating_run_id": "run-1",
        "run_fence_generation": 1,
        "assistant_message_index": None,
        "next_tool_call_index": 0,
        "current_tool_call_id": None,
        "current_tool_name": None,
        "model_turns_used": 1,
        "tool_calls_used": 2,
        "remaining_runtime_seconds": 12.5,
        "started_at": _fixed_time(),
        "deadline_at": _fixed_time() + timedelta(seconds=60),
        "updated_at": _fixed_time(),
    }


def _fixed_time() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
