
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    # Store only a digest of the bearer token; the raw value exists only in the
    # HttpOnly cookie returned at login.
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="sessions")


class QuizAttempt(Base):
    """A durable quiz run and its final score for one InfoByte user."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint("question_count > 0", name="ck_quiz_attempts_question_count_positive"),
        CheckConstraint(
            "status IN ('in_progress', 'completed')", name="ck_quiz_attempts_status_valid"
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= question_count)",
            name="ck_quiz_attempts_score_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[int] = mapped_column(nullable=False)
    test_title: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int | None] = mapped_column(nullable=True)
    question_count: Mapped[int] = mapped_column(nullable=False)
    retry_of_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    owner: Mapped[User] = relationship(back_populates="quiz_attempts")
    questions: Mapped[list["QuizAttemptAnswer"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="QuizAttemptAnswer.position",
        passive_deletes=True,
    )


class QuizAttemptAnswer(Base):
    """Per-question content snapshot, selection, and answer key for an attempt."""

    __tablename__ = "quiz_attempt_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_quiz_attempt_answers_question"),
        CheckConstraint("position >= 0", name="ck_quiz_attempt_answers_position_nonnegative"),
        CheckConstraint(
            "selected_option IS NULL OR selected_option >= 0",
            name="ck_quiz_attempt_answers_selected_nonnegative",
        ),
        CheckConstraint("correct_option >= 0", name="ck_quiz_attempt_answers_correct_nonnegative"),
    )

    attempt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(180), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    level: Mapped[str] = mapped_column(String(80), nullable=False)
    selected_option: Mapped[int | None] = mapped_column(nullable=True)
    correct_option: Mapped[int] = mapped_column(nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    attempt: Mapped[QuizAttempt] = relationship(back_populates="questions")
