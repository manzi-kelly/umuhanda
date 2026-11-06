from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.exam_results import result_view


@pytest.mark.parametrize(
    ("correct", "incorrect", "unanswered", "status", "percentage"),
    [
        (0, 0, 20, "FAILED", 0),
        (11, 3, 6, "FAILED", 55),
        (12, 7, 1, "PASSED", 60),
        (20, 0, 0, "PASSED", 100),
    ],
)
def test_result_projection(correct, incorrect, unanswered, status, percentage):
    started = datetime(2026, 11, 5, 10, tzinfo=UTC)
    completed = started.replace(minute=20)
    attempt = SimpleNamespace(id=uuid4(), started_at=started)
    timing = SimpleNamespace(completion_reason="GLOBAL_TIME_EXPIRED")
    stored = SimpleNamespace(
        student_name="Synthetic Student",
        correct=correct,
        incorrect=incorrect,
        unanswered=unanswered,
        completed_at=completed,
        correct_index=1,
    )
    assert result_view(attempt, timing, stored).model_dump() == {
        "attemptId": attempt.id,
        "studentName": "Synthetic Student",
        "startedAt": started,
        "completedAt": completed,
        "completionReason": "GLOBAL_TIME_EXPIRED",
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "score": correct,
        "total": 20,
        "percentage": percentage,
        "status": status,
    }
