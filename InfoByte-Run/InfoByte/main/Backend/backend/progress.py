"""Per-user learning progress derived from durable quiz attempts."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .database import get_db
from .models import QuizAttempt
from .routes import current_user

router = APIRouter(prefix="/api", tags=["Progress"])


def _percent(correct: int, total: int) -> int:
    return int(100 * correct / total + 0.5) if total else 0


@router.get("/progress")
def get_progress(db: Session = Depends(get_db), user=Depends(current_user)):
    attempts = db.scalars(
        select(QuizAttempt)
        .options(selectinload(QuizAttempt.questions))
        .where(QuizAttempt.owner_id == user.id)
        .order_by(QuizAttempt.started_at.desc())
    ).all()
    completed = [attempt for attempt in attempts if attempt.status == "completed"]
    in_progress = len(attempts) - len(completed)

    total_questions = 0
    correct_answers = 0
    topic_stats: dict[str, dict] = {}
    recent = []
    best_percent = 0

    for attempt in completed:
        attempt_total = len(attempt.questions)
        attempt_correct = sum(
            question.selected_option == question.correct_option
            for question in attempt.questions
        )
        attempt_percent = _percent(attempt_correct, attempt_total)
        total_questions += attempt_total
        correct_answers += attempt_correct
        best_percent = max(best_percent, attempt_percent)

        for question in attempt.questions:
            bucket = topic_stats.setdefault(
                question.topic, {"subject": question.topic, "total": 0, "correct": 0}
            )
            bucket["total"] += 1
            bucket["correct"] += question.selected_option == question.correct_option

        recent.append(
            {
                "id": str(attempt.id),
                "topic": attempt.test_title,
                "total": attempt_total,
                "correct": attempt_correct,
                "percent": attempt_percent,
                "finished_at": attempt.finished_at,
                "started_at": attempt.started_at,
            }
        )

    topic_rows = []
    for item in topic_stats.values():
        item["percent"] = _percent(item["correct"], item["total"])
        topic_rows.append(item)
    topic_rows.sort(key=lambda item: (-item["percent"], item["subject"]))

    return {
        "summary": {
            "tests_completed": len(completed),
            "tests_in_progress": in_progress,
            "questions_answered": total_questions,
            "correct_answers": correct_answers,
            "accuracy": _percent(correct_answers, total_questions),
            "best_percent": best_percent,
        },
        "topics": topic_rows,
        "recent_attempts": recent[:10],
    }
