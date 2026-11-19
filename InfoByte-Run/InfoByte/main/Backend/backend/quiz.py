"""PostgreSQL-backed quizzes with private, immutable question snapshots."""
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .database import get_db
from .models import QuizAttempt, QuizAttemptAnswer
from .routes import current_user
from .schemas import (
    AttemptAnswerInput,
    AttemptHistoryItem,
    AttemptView,
    DraftAttemptAnswer,
    LegacyAnswerInput,
    LegacyStartAttempt,
    MistakeReviewInput,
    StartAttempt,
    SubmitAttempt,
)

router = APIRouter(prefix="/api", tags=["ҰБТ тесттері"])
bank = json.loads(Path(__file__).with_name("questions.json").read_text("utf-8-sig"))
questions = {item["id"]: item for item in bank["questions"]}
topics = bank["topics"]


def _percent(score: int, total: int) -> int:
    return int(100 * score / total + 0.5) if total else 0


def _topic_id(question_id: int) -> int:
    return min((question_id - 1) // 20 + 1, len(topics))


def _topic_title(question_id: int) -> str:
    return topics[_topic_id(question_id) - 1]


def _load_owned(
    db: Session, attempt_id: UUID, owner_id: UUID, *, lock: bool = False
) -> QuizAttempt:
    statement = (
        select(QuizAttempt)
        .options(selectinload(QuizAttempt.questions))
        .where(QuizAttempt.id == attempt_id, QuizAttempt.owner_id == owner_id)
    )
    if lock:
        statement = statement.with_for_update()
    attempt = db.scalar(statement)
    if attempt is None:
        # Do not disclose whether another user's attempt ID exists.
        raise HTTPException(404, "Тест нәтижесі табылмады.")
    return attempt


def _attempt_view(attempt: QuizAttempt) -> dict:
    completed = attempt.status == "completed"
    rows = []
    for question in attempt.questions:
        row = {
            "position": question.position,
            "question_id": question.question_id,
            "topic": question.topic,
            "text": question.question_text,
            "options": question.options,
            "level": question.level,
            "selected_option_index": question.selected_option,
        }
        if completed:
            row["correct_option_index"] = question.correct_option
            if question.selected_option is None:
                row["status"] = "unanswered"
            elif question.selected_option == question.correct_option:
                row["status"] = "correct"
            else:
                row["status"] = "incorrect"
        rows.append(row)

    percent = None
    if completed and attempt.question_count:
        percent = _percent(attempt.score or 0, attempt.question_count)
    return {
        "id": attempt.id,
        "test_id": attempt.test_id,
        "test_title": attempt.test_title,
        "status": attempt.status,
        "started_at": attempt.started_at,
        "finished_at": attempt.finished_at,
        "score": attempt.score,
        "question_count": attempt.question_count,
        "percent": percent,
        "retry_of_id": attempt.retry_of_id,
        "questions": rows,
    }


def _legacy_view(attempt: QuizAttempt) -> dict:
    """Keep the previous tests.js response keys available to cached clients."""
    payload = _attempt_view(attempt)
    payload["finished"] = attempt.status == "completed"
    for question in payload["questions"]:
        question["id"] = question.pop("question_id")
        question["choice"] = question.pop("selected_option_index", None)
        if attempt.status == "completed":
            question["key"] = question.pop("correct_option_index")
    return payload


def _make_attempt(
    db: Session,
    owner_id: UUID,
    test_id: int,
    title: str,
    chosen_questions: list[dict],
    *,
    retry_of_id: UUID | None = None,
) -> QuizAttempt:
    attempt = QuizAttempt(
        owner_id=owner_id,
        test_id=test_id,
        test_title=title,
        status="in_progress",
        question_count=len(chosen_questions),
        retry_of_id=retry_of_id,
    )
    for position, source in enumerate(chosen_questions):
        source_id = source["id"]
        topic = _topic_title(source_id)
        attempt.questions.append(
            QuizAttemptAnswer(
                position=position,
                question_id=source_id,
                topic=topic,
                question_text=source["text"],
                options=list(source["options"]),
                level=source.get("level", ""),
                correct_option=source["key"],
                explanation=(
                    source.get("analysis") or source.get("explanation") or source.get("rationale")
                ),
            )
        )
    db.add(attempt)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(attempt)
    return attempt


def _start_attempt(db: Session, owner_id: UUID, test_id: int, count: int) -> dict:
    if test_id < 0 or test_id > len(topics):
        raise HTTPException(404, "Тест тақырыбы табылмады.")

    pool = [
        question
        for question in bank["questions"]
        if test_id == 0 or _topic_id(question["id"]) == test_id
    ]
    if not pool:
        raise HTTPException(409, "Бұл тақырыпта әзірге сұрақ жоқ.")
    if count > len(pool):
        raise HTTPException(422, f"Бұл тестте {len(pool)} сұрақ қана бар.")

    title = "Аралас тест" if test_id == 0 else topics[test_id - 1]
    attempt = _make_attempt(db, owner_id, test_id, title, random.sample(pool, count))
    return _attempt_view(attempt)


def _save_draft(
    db: Session,
    attempt_id: UUID,
    owner_id: UUID,
    question_id: int,
    selected_option_index: int | None,
) -> dict:
    attempt = _load_owned(db, attempt_id, owner_id, lock=True)
    if attempt.status != "in_progress":
        raise HTTPException(409, "Аяқталған тесттің жауаптарын өзгертуге болмайды.")
    question = next((row for row in attempt.questions if row.question_id == question_id), None)
    if question is None:
        raise HTTPException(422, "Бұл сұрақ осы тестке кірмейді.")
    if selected_option_index is not None and selected_option_index >= len(question.options):
        raise HTTPException(422, "Таңдалған нұсқа бұл сұраққа тиесілі емес.")

    question.selected_option = selected_option_index
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _attempt_view(attempt)


def _submit(
    db: Session,
    attempt_id: UUID,
    owner_id: UUID,
    answers: list[AttemptAnswerInput] | None,
) -> dict:
    attempt = _load_owned(db, attempt_id, owner_id, lock=True)
    if attempt.status == "completed":
        # A retry of the same request returns the saved result without rewriting it.
        return _attempt_view(attempt)

    if answers is not None:
        submitted: dict[int, int | None] = {}
        for answer in answers:
            if answer.question_id in submitted:
                raise HTTPException(422, "Бір сұраққа екі жауап жіберілді.")
            submitted[answer.question_id] = answer.selected_option_index

        questions_by_id = {question.question_id: question for question in attempt.questions}
        unknown_ids = submitted.keys() - questions_by_id.keys()
        if unknown_ids:
            raise HTTPException(422, "Жауаптардың ішінде осы тестке кірмейтін сұрақ бар.")
        for question_id, selected in submitted.items():
            question = questions_by_id[question_id]
            if selected is not None and selected >= len(question.options):
                raise HTTPException(422, "Таңдалған нұсқа бұл сұраққа тиесілі емес.")

        # The request is authoritative, including explicit nulls for unanswered items.
        for question in attempt.questions:
            question.selected_option = submitted.get(question.question_id)

    score = sum(
        question.selected_option is not None
        and question.selected_option == question.correct_option
        for question in attempt.questions
    )
    attempt.score = score
    attempt.status = "completed"
    attempt.finished_at = datetime.now(timezone.utc)
    try:
        # Answer snapshots and the final score are committed atomically.
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _attempt_view(attempt)


def _history(db: Session, owner_id: UUID) -> list[dict]:
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.owner_id == owner_id, QuizAttempt.status == "completed")
        .order_by(QuizAttempt.finished_at.desc(), QuizAttempt.started_at.desc())
    ).all()
    return [
        {
            "id": attempt.id,
            "test_id": attempt.test_id,
            "test_title": attempt.test_title,
            "finished_at": attempt.finished_at,
            "score": attempt.score or 0,
            "question_count": attempt.question_count,
            "percent": _percent(attempt.score or 0, attempt.question_count),
        }
        for attempt in attempts
    ]


def _mistake_view(attempt: QuizAttempt, question: QuizAttemptAnswer) -> dict:
    selected = question.selected_option
    if question.explanation:
        explanation = question.explanation
    elif selected is None:
        explanation = (
            f"Сұраққа жауап берілмеді. Дұрыс жауап — «{question.options[question.correct_option]}»."
        )
    else:
        explanation = (
            f"Бұл сұрақ «{question.topic}» тақырыбын тексереді. Дұрыс жауап — "
            f"«{question.options[question.correct_option]}», ал сіз "
            f"«{question.options[selected]}» деп таңдадыңыз."
        )
    return {
        "attempt_id": attempt.id,
        "question_id": question.question_id,
        "topic": question.topic,
        "level": question.level,
        "question": question.question_text,
        "options": question.options,
        "selected": selected,
        "correct": question.correct_option,
        "analysis": explanation,
        "reviewed": question.reviewed,
    }


@router.get("/test-topics")
def get_topics():
    return topics


@router.post("/tests/{test_id}/attempts", response_model=AttemptView, response_model_exclude_none=True, status_code=201)
def start_test(
    test_id: int,
    data: StartAttempt,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    return _start_attempt(db, user.id, test_id, data.count)


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptView, response_model_exclude_none=True)
def submit_attempt(
    attempt_id: UUID,
    data: SubmitAttempt,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    return _submit(db, attempt_id, user.id, data.answers)


@router.get("/me/attempts", response_model=list[AttemptHistoryItem])
def my_attempts(db: Session = Depends(get_db), user=Depends(current_user)):
    return _history(db, user.id)


@router.get("/attempts/{attempt_id}", response_model=AttemptView, response_model_exclude_none=True)
def get_attempt(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    return _attempt_view(_load_owned(db, attempt_id, user.id))


@router.post(
    "/attempts/{attempt_id}/retry-mistakes",
    response_model=AttemptView,
    response_model_exclude_none=True,
    status_code=201,
)
def retry_mistakes(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    original = _load_owned(db, attempt_id, user.id, lock=True)
    if original.status != "completed":
        raise HTTPException(409, "Қателерді тек аяқталған тесттен қайталауға болады.")
    missed = [
        question
        for question in original.questions
        if question.selected_option != question.correct_option
    ]
    if not missed:
        raise HTTPException(409, "Қайталауға қате немесе жауапсыз сұрақ жоқ.")

    retry = QuizAttempt(
        owner_id=user.id,
        test_id=original.test_id,
        test_title=original.test_title,
        status="in_progress",
        question_count=len(missed),
        retry_of_id=original.id,
    )
    for position, question in enumerate(missed):
        retry.questions.append(
            QuizAttemptAnswer(
                position=position,
                question_id=question.question_id,
                topic=question.topic,
                question_text=question.question_text,
                options=list(question.options),
                level=question.level,
                correct_option=question.correct_option,
                explanation=question.explanation,
            )
        )
    db.add(retry)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(retry)
    return _attempt_view(retry)


@router.patch("/attempts/{attempt_id}/answers", response_model=AttemptView, response_model_exclude_none=True)
def save_attempt_answer(
    attempt_id: UUID,
    data: DraftAttemptAnswer,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    return _save_draft(
        db, attempt_id, user.id, data.question_id, data.selected_option_index
    )


@router.get("/mistakes")
def get_mistakes(db: Session = Depends(get_db), user=Depends(current_user)):
    completed = db.scalars(
        select(QuizAttempt)
        .options(selectinload(QuizAttempt.questions))
        .where(QuizAttempt.owner_id == user.id, QuizAttempt.status == "completed")
        .order_by(QuizAttempt.finished_at.desc())
    ).all()
    items = [
        _mistake_view(attempt, question)
        for attempt in completed
        for question in attempt.questions
        if question.selected_option != question.correct_option
    ]
    reviewed = sum(item["reviewed"] for item in items)
    return {
        "items": items,
        "total": len(items),
        "reviewed": reviewed,
        "pending": len(items) - reviewed,
    }


@router.post("/mistakes/review")
def set_mistake_review(
    data: MistakeReviewInput,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    attempt = _load_owned(db, data.attempt_id, user.id, lock=True)
    if attempt.status != "completed":
        raise HTTPException(409, "Тест аяқталғаннан кейін ғана қатені белгілеуге болады.")
    question = next(
        (row for row in attempt.questions if row.question_id == data.question_id), None
    )
    if question is None or question.selected_option == question.correct_option:
        raise HTTPException(404, "Қате жауап табылмады.")
    question.reviewed = data.reviewed
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _mistake_view(attempt, question)


# Compatibility routes for the earlier tests.js client and existing integrations.
@router.post("/test-attempts", status_code=201)
def legacy_start_test(
    data: LegacyStartAttempt,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    started = _start_attempt(db, user.id, data.topic, data.count)
    return {"id": started["id"]}


@router.get("/test-attempts")
def legacy_history(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.owner_id == user.id)
        .order_by(QuizAttempt.started_at.desc())
    ).all()
    return [
        {"id": row.id, "count": row.question_count, "finished": row.status == "completed"}
        for row in rows
    ]


@router.get("/test-attempts/{attempt_id}")
def legacy_get_attempt(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    return _legacy_view(_load_owned(db, attempt_id, user.id))


@router.patch("/test-attempts/{attempt_id}/answers")
def legacy_save_answer(
    attempt_id: UUID,
    data: LegacyAnswerInput,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    _save_draft(db, attempt_id, user.id, data.question, data.choice)
    return _legacy_view(_load_owned(db, attempt_id, user.id))


@router.post("/test-attempts/{attempt_id}/submit")
def legacy_submit(
    attempt_id: UUID,
    data: SubmitAttempt | None = Body(default=None),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    _submit(db, attempt_id, user.id, data.answers if data is not None else None)
    return _legacy_view(_load_owned(db, attempt_id, user.id))


@router.post("/test-attempts/{attempt_id}/retry", status_code=201)
def legacy_retry(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    retry = retry_mistakes(attempt_id, db, user)
    return {"id": retry["id"]}
