import unittest
from datetime import datetime, timedelta, timezone

from agent.runtime.continuation import AgentContinuation


class AgentContinuationTest(unittest.TestCase):
    def test_valid_continuation_can_be_created(self) -> None:
        started_at = _fixed_time()
        continuation = AgentContinuation(
            originating_run_id="run-1",
            assistant_message_index=2,
            next_tool_call_index=1,
            model_turns_used=1,
            tool_calls_used=3,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
        )

        self.assertEqual(continuation.originating_run_id, "run-1")
        self.assertEqual(continuation.assistant_message_index, 2)
        self.assertEqual(continuation.next_tool_call_index, 1)
        self.assertEqual(continuation.started_at.tzinfo, timezone.utc)
        self.assertEqual(continuation.remaining_runtime_seconds, 60)

    def test_explicit_remaining_runtime_seconds_is_preserved(self) -> None:
        started_at = _fixed_time()
        continuation = AgentContinuation(
            **{
                **_valid_kwargs(started_at),
                "remaining_runtime_seconds": 12.5,
            }
        )

        self.assertEqual(continuation.remaining_runtime_seconds, 12.5)

    def test_negative_remaining_runtime_seconds_is_rejected(self) -> None:
        started_at = _fixed_time()
        kwargs = _valid_kwargs(started_at)
        kwargs["remaining_runtime_seconds"] = -0.1

        with self.assertRaises(ValueError):
            AgentContinuation(**kwargs)

    def test_negative_message_or_tool_index_is_rejected(self) -> None:
        started_at = _fixed_time()
        for field_name in ("assistant_message_index", "next_tool_call_index"):
            with self.subTest(field_name=field_name):
                kwargs = _valid_kwargs(started_at)
                kwargs[field_name] = -1

                with self.assertRaises(ValueError):
                    AgentContinuation(**kwargs)

    def test_negative_counts_are_rejected(self) -> None:
        started_at = _fixed_time()
        for field_name in ("model_turns_used", "tool_calls_used"):
            with self.subTest(field_name=field_name):
                kwargs = _valid_kwargs(started_at)
                kwargs[field_name] = -1

                with self.assertRaises(ValueError):
                    AgentContinuation(**kwargs)

    def test_naive_datetime_is_rejected(self) -> None:
        started_at = datetime(2026, 1, 2, 3, 4, 5)
        kwargs = _valid_kwargs(_fixed_time())
        kwargs["started_at"] = started_at

        with self.assertRaises(ValueError):
            AgentContinuation(**kwargs)

    def test_deadline_before_started_at_is_rejected(self) -> None:
        started_at = _fixed_time()
        kwargs = _valid_kwargs(started_at)
        kwargs["deadline_at"] = started_at - timedelta(seconds=1)

        with self.assertRaises(ValueError):
            AgentContinuation(**kwargs)


def _valid_kwargs(started_at: datetime) -> dict:
    return {
        "originating_run_id": "run-1",
        "assistant_message_index": 2,
        "next_tool_call_index": 1,
        "model_turns_used": 1,
        "tool_calls_used": 3,
        "started_at": started_at,
        "deadline_at": started_at + timedelta(seconds=60),
    }


def _fixed_time() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
